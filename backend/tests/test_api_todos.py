from __future__ import annotations

from pathlib import Path
import sqlite3
from uuid import UUID

from fastapi.testclient import TestClient

from inkpi.api import create_app


class FakeDisplayRenderer:
    def __init__(self) -> None:
        self.revisions: list[str] = []
        self.text_renders: list[tuple[str, str]] = []
        self.closed = False

    def render_png(self, revision: str) -> bytes:
        self.revisions.append(revision)
        return b"fake-png"

    def render_text_png(self, content: str, revision: str) -> bytes:
        self.text_renders.append((content, revision))
        return b"fake-text-png"

    def close(self) -> None:
        self.closed = True


def _database_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def test_todo_crud_reordering_and_display_revision(tmp_path: Path) -> None:
    app = create_app(_database_url(tmp_path / "inkpi.db"))

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        initial_revision = client.get("/api/display/revision").json()["revision"]
        UUID(initial_revision)

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
        second_revision = client.get("/api/display/revision").json()["revision"]
        assert second_revision != initial_revision

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
        assert client.get("/api/display/revision").json()["revision"] != second_revision


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
        UUID(client.get("/api/display/revision").json()["revision"])


def test_todo_display_settings_persist_and_bump_revision(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "todo-display.db")
    with TestClient(create_app(database_url)) as client:
        assert client.get("/api/settings/todos/display").json() == {
            "show_completed": True, "sort": "manual"
        }
        before = client.get("/api/display/revision").json()["revision"]
        updated = client.put(
            "/api/settings/todos/display",
            json={"show_completed": False, "sort": "completed_asc"},
        )
        assert updated.status_code == 200
        assert updated.json() == {"show_completed": False, "sort": "completed_asc"}
        assert client.get("/api/display/revision").json()["revision"] != before

    with TestClient(create_app(database_url)) as client:
        assert client.get("/api/settings/todos/display").json() == {
            "show_completed": False, "sort": "completed_asc"
        }


def test_todo_display_settings_reject_invalid_sort(tmp_path: Path) -> None:
    with TestClient(create_app(_database_url(tmp_path / "todo-sort.db"))) as client:
        response = client.put(
            "/api/settings/todos/display",
            json={"show_completed": True, "sort": "alphabetical"},
        )
        assert response.status_code == 422


def test_legacy_integer_revision_is_migrated_to_uuid(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-revision.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE display_state ("
            "id INTEGER PRIMARY KEY, revision INTEGER NOT NULL, updated_at DATETIME NOT NULL, "
            "last_refresh DATETIME, last_full_refresh DATETIME, refresh_count INTEGER NOT NULL)"
        )
        connection.execute(
            "INSERT INTO display_state VALUES (1, 9223372036854775807, CURRENT_TIMESTAMP, NULL, NULL, 0)"
        )

    with TestClient(create_app(_database_url(database_path))) as client:
        revision = client.get("/api/display/revision").json()["revision"]
        UUID(revision)
        assert revision != "9223372036854775807"


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
        revision = client.get("/api/display/revision").json()["revision"]
        response = client.get("/api/display/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["x-inkpi-revision"] == revision
        assert response.headers["etag"] == f'"inkpi-{revision}"'
        assert response.content == b"fake-png"
        assert renderer.revisions == [revision]

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
        revision = client.get("/api/display/revision").json()["revision"]
        denied = client.post(
            "/api/display/refresh",
            json={"revision": revision, "action": "full", "accepted": True},
        )
        assert denied.status_code == 401

        reported = client.post(
            "/api/display/refresh",
            headers={"Authorization": "Bearer display-secret"},
            json={"revision": revision, "action": "full", "accepted": True},
        )
        assert reported.status_code == 204
        system = client.get("/api/settings/system").json()
        assert system["display_revision"] == revision
        assert system["last_refresh"] is not None
        assert system["uptime_seconds"] >= 0
        assert system["firmware_version"]

        stale = client.post(
            "/api/display/refresh",
            headers={"Authorization": "Bearer display-secret"},
            json={"revision": str(UUID(int=0)), "action": "partial", "accepted": True},
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
        UUID(client.get("/api/display/revision").json()["revision"])

        latest = client.get("/api/reports/latest").json()
        assert len(latest) == 1
        assert latest[0]["agent_name"] == "ubuntu-main"
        assert latest[0]["payload"]["weekly_used_percent"] == 72
