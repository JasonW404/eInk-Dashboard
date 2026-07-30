from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from inkpi.api import create_app
from inkpi.network.auth import AdminAuthPolicy
from test_api_todos import FakeDisplayRenderer, _database_url


def test_integration_settings_require_session_and_mask_token(tmp_path: Path) -> None:
    app = create_app(
        _database_url(tmp_path / "integrations.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
        admin_auth=AdminAuthPolicy(token="admin-secret"),
    )

    with TestClient(app) as client:
        assert client.get("/api/settings/integrations").status_code == 401
        login = client.post("/api/auth/login", json={"token": "admin-secret"})
        csrf = login.json()["csrf_token"]

        saved = client.put(
            "/api/settings/integrations/github",
            headers={"X-CSRF-Token": csrf},
            json={
                "enabled": False,
                "username": "octocat",
                "organization": "github",
                "extra_repos": ["openai/openai-python"],
                "token": "github-secret",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["github"]["token_configured"] is True
        assert "github-secret" not in saved.text
        assert saved.json()["codex"]["api_key_supported"] is False

        read = client.get("/api/settings/integrations")
        assert read.json()["github"]["username"] == "octocat"
        assert "token" not in read.json()["github"]


def test_github_integration_validation_and_token_removal(tmp_path: Path) -> None:
    app = create_app(
        _database_url(tmp_path / "integration-validation.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
        admin_auth=AdminAuthPolicy(token="admin-secret"),
    )
    with TestClient(app) as client:
        csrf = client.post("/api/auth/login", json={"token": "admin-secret"}).json()["csrf_token"]
        missing_user = client.put(
            "/api/settings/integrations/github",
            headers={"X-CSRF-Token": csrf},
            json={"enabled": True, "username": ""},
        )
        assert missing_user.status_code == 422

        invalid_repo = client.put(
            "/api/settings/integrations/github",
            headers={"X-CSRF-Token": csrf},
            json={"enabled": False, "username": "octocat", "extra_repos": ["invalid"]},
        )
        assert invalid_repo.status_code == 422

        cleared = client.put(
            "/api/settings/integrations/github",
            headers={"X-CSRF-Token": csrf},
            json={"enabled": False, "username": "octocat", "clear_token": True},
        )
        assert cleared.status_code == 200
        assert cleared.json()["github"]["token_configured"] is False
