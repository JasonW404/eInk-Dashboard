from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from inkpi.api import create_app


class FakeDisplayRenderer:
    def __init__(self) -> None:
        self.revisions: list[int] = []
        self.closed = False

    def render_png(self, revision: int) -> bytes:
        self.revisions.append(revision)
        return b"fake-png"

    def close(self) -> None:
        self.closed = True


def _database_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def test_todo_crud_reordering_and_display_revision(tmp_path: Path) -> None:
    app = create_app(_database_url(tmp_path / "inkpi.db"))

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/display/revision").json()["revision"] == 0

        first_response = client.post(
            "/api/todos",
            json={"title": "  Refactor API  ", "display_on_eink": True},
        )
        assert first_response.status_code == 201
        first = first_response.json()
        assert first["title"] == "Refactor API"
        assert first["sort_order"] == 0

        second = client.post(
            "/api/todos",
            json={"title": "Build web UI", "display_on_eink": False},
        ).json()
        assert second["sort_order"] == 1
        assert client.get("/api/display/revision").json()["revision"] == 2

        updated_response = client.patch(f"/api/todos/{first['id']}", json={"completed": True})
        assert updated_response.status_code == 200
        assert updated_response.json()["completed"] is True

        reordered_response = client.put("/api/todos/order", json={"ordered_ids": [second["id"], first["id"]]})
        assert reordered_response.status_code == 200
        assert [item["id"] for item in reordered_response.json()] == [second["id"], first["id"]]

        delete_response = client.delete(f"/api/todos/{second['id']}")
        assert delete_response.status_code == 204
        remaining = client.get("/api/todos").json()
        assert [item["id"] for item in remaining] == [first["id"]]
        assert remaining[0]["sort_order"] == 0
        assert client.get("/api/display/revision").json()["revision"] == 5


def test_todo_api_validates_payloads_and_order(tmp_path: Path) -> None:
    app = create_app(_database_url(tmp_path / "validation.db"))

    with TestClient(app) as client:
        assert client.post("/api/todos", json={"title": "   "}).status_code == 422
        created = client.post("/api/todos", json={"title": "One"}).json()
        assert client.patch("/api/todos/404", json={"completed": True}).status_code == 404
        assert client.delete("/api/todos/404").status_code == 404

        duplicate_order = client.put("/api/todos/order", json={"ordered_ids": [created["id"], created["id"]]})
        assert duplicate_order.status_code == 400


def test_todos_persist_across_app_restarts(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "persistent.db")

    with TestClient(create_app(database_url)) as client:
        client.post("/api/todos", json={"title": "Persist me"})

    with TestClient(create_app(database_url)) as client:
        todos = client.get("/api/todos").json()
        assert [todo["title"] for todo in todos] == ["Persist me"]
        assert client.get("/api/display/revision").json()["revision"] == 1


def test_api_serves_built_web_routes_when_available(tmp_path: Path) -> None:
    web_dist = tmp_path / "dist"
    assets = web_dist / "assets"
    assets.mkdir(parents=True)
    (web_dist / "index.html").write_text("<h1>InkPi Web</h1>", encoding="utf-8")
    (web_dist / "eink.html").write_text("<main>InkPi eInk</main>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('inkpi')", encoding="utf-8")

    app = create_app(_database_url(tmp_path / "web.db"), web_dist=web_dist)
    with TestClient(app) as client:
        assert client.get("/").text == "<h1>InkPi Web</h1>"
        assert client.get("/todo").status_code == 200
        assert client.get("/settings").status_code == 200
        assert client.get("/eink.html").text == "<main>InkPi eInk</main>"
        assert client.get("/assets/app.js").status_code == 200


def test_display_image_uses_current_revision_and_closes_renderer(tmp_path: Path) -> None:
    renderer = FakeDisplayRenderer()
    app = create_app(
        _database_url(tmp_path / "display-image.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=renderer,
    )

    with TestClient(app) as client:
        client.post("/api/todos", json={"title": "Visible item"})
        response = client.get("/api/display/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["x-inkpi-revision"] == "1"
        assert response.headers["etag"] == '"inkpi-1"'
        assert response.content == b"fake-png"
        assert renderer.revisions == [1]

    assert renderer.closed is True


def test_display_refresh_telemetry_updates_read_only_system_info(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("INKPI_DISPLAY_TOKEN", "display-secret")
    app = create_app(
        _database_url(tmp_path / "display-telemetry.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
    )

    with TestClient(app) as client:
        client.post("/api/todos", json={"title": "Visible item"})
        denied = client.post(
            "/api/display/refresh",
            json={"revision": 1, "action": "full", "accepted": True},
        )
        assert denied.status_code == 401

        reported = client.post(
            "/api/display/refresh",
            headers={"Authorization": "Bearer display-secret"},
            json={"revision": 1, "action": "full", "accepted": True},
        )
        assert reported.status_code == 204
        system = client.get("/api/settings/system").json()
        assert system["display_revision"] == 1
        assert system["last_refresh"] is not None
        assert system["uptime_seconds"] >= 0
        assert system["firmware_version"]

        stale = client.post(
            "/api/display/refresh",
            headers={"Authorization": "Bearer display-secret"},
            json={"revision": 0, "action": "partial", "accepted": True},
        )
        assert stale.status_code == 409


def test_agent_registration_heartbeat_and_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INKPI_AGENT_ENROLLMENT_TOKEN", "enroll-secret")
    app = create_app(
        _database_url(tmp_path / "agents.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
    )

    with TestClient(app) as client:
        denied = client.post(
            "/api/agents/register",
            json={"name": "ubuntu-main", "enrollment_token": "wrong"},
        )
        assert denied.status_code == 403

        registration = client.post(
            "/api/agents/register",
            json={"name": "ubuntu-main", "enrollment_token": "enroll-secret"},
        )
        assert registration.status_code == 201
        credentials = registration.json()
        headers = {"Authorization": f"Bearer {credentials['token']}"}

        heartbeat = client.post(
            f"/api/agents/{credentials['id']}/heartbeat",
            headers=headers,
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["name"] == "ubuntu-main"

        unauthorized = client.post(
            f"/api/agents/{credentials['id']}/reports",
            json={"type": "codex", "payload": {"plan": "pro"}},
        )
        assert unauthorized.status_code == 401

        report = client.post(
            f"/api/agents/{credentials['id']}/reports",
            headers=headers,
            json={
                "type": "CODEX",
                "payload": {"plan": "pro", "weekly_used_percent": 72},
                "ttl_seconds": 3600,
            },
        )
        assert report.status_code == 201
        assert report.json()["type"] == "codex"
        assert client.get("/api/display/revision").json()["revision"] == 1

        latest = client.get("/api/reports/latest").json()
        assert len(latest) == 1
        assert latest[0]["agent_name"] == "ubuntu-main"
        assert latest[0]["payload"]["weekly_used_percent"] == 72
