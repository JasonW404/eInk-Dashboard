from __future__ import annotations

import io
import importlib
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from inkpi.api import create_app
from inkpi.network.auth import AdminAuthPolicy
from inkpi.network.operations import InMemoryNetworkHelper
from tests.test_api_todos import FakeDisplayRenderer, _database_url


def _png(size: tuple[int, int] = (320, 200)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, "black").save(output, "PNG")
    return output.getvalue()


def test_photo_pages_upload_update_reorder_and_delete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INKPI_UPLOAD_DIR", str(tmp_path / "uploads"))
    app = create_app(
        _database_url(tmp_path / "pages.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
        admin_auth=AdminAuthPolicy(token="admin-secret"),
    )

    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"token": "admin-secret"}).json()
        headers = {"X-CSRF-Token": login["csrf_token"]}
        first = client.post("/api/pages", headers={**headers, "X-File-Name": "one.jpg"}, content=_png())
        second = client.post("/api/pages", headers={**headers, "X-File-Name": "two.png"}, content=_png())
        assert first.status_code == 201
        assert second.status_code == 201
        first_id, second_id = first.json()["id"], second.json()["id"]
        preview = client.get(f"/api/pages/{first_id}/image")
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/png"
        stored = list((tmp_path / "uploads").glob("*.png"))
        assert len(stored) == 2
        with Image.open(stored[0]) as normalized:
            assert normalized.size == (800, 480)

        updated = client.patch(
            f"/api/pages/{first_id}", headers=headers, json={"interval_seconds": 300, "enabled": False}
        )
        assert updated.json()["interval_seconds"] == 300
        assert updated.json()["enabled"] is False

        reordered = client.put(
            "/api/pages/order", headers=headers, json={"ordered_ids": [second_id, 0, first_id]}
        )
        assert [page["id"] for page in reordered.json()] == [second_id, 0, first_id]

        deleted = client.delete(f"/api/pages/{first_id}", headers=headers)
        assert deleted.status_code == 204
        assert [page["id"] for page in client.get("/api/pages").json()] == [second_id, 0]


def test_playlist_advances_from_dashboard_to_photo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INKPI_UPLOAD_DIR", str(tmp_path / "uploads"))
    app_module = importlib.import_module("inkpi.api.app")
    monkeypatch.setattr(app_module.time, "time", lambda: 61)
    app = create_app(
        _database_url(tmp_path / "playlist.db"), web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(), admin_auth=AdminAuthPolicy(token="admin-secret"),
    )
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"token": "admin-secret"}).json()
        uploaded = client.post(
            "/api/pages", headers={"X-CSRF-Token": login["csrf_token"], "X-File-Name": "page.png"},
            content=_png(),
        )
        assert uploaded.status_code == 201
        revision = client.get("/api/display/revision").json()["revision"]
        image = client.get("/api/display/image")
        assert image.status_code == 200
        assert image.headers["X-InkPi-Revision"] == revision
        with Image.open(io.BytesIO(image.content)) as rendered:
            assert rendered.size == (800, 480)


def test_open_hotspot_needs_no_password_and_has_no_secret(tmp_path: Path) -> None:
    helper = InMemoryNetworkHelper()
    app = create_app(
        _database_url(tmp_path / "open-network.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
        network_helper=helper,
        admin_auth=AdminAuthPolicy(token="admin-secret"),
        hotspot_active_checker=lambda: True,
    )
    with TestClient(app) as client:
        enabled = client.put(
            "/api/settings/network/hotspot",
            headers={"X-Admin-Token": "admin-secret"},
            json={"enabled": True, "ssid": "InkPi Open", "security": "open"},
        )
        assert enabled.status_code == 200
        assert enabled.json()["security"] == "open"
        assert enabled.json()["operation"]["safe_details"]["security"] == "open"

        login = client.post("/api/auth/login", json={"token": "admin-secret"})
        assert login.status_code == 200
        assert client.get("/api/settings/network/hotspot/credentials").json() == {"password": None}
        assert client.get("/api/display/context").json()["wifi_qr_payload"] == "WIFI:T:nopass;S:InkPi Open;;"
