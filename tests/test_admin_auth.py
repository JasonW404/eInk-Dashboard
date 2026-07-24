from __future__ import annotations

import pytest

from inkpi.admin.auth import AdminAuthError, AdminAuthPolicy, extract_bearer_token


def test_admin_auth_rejects_mutations_when_token_is_not_configured() -> None:
    with pytest.raises(AdminAuthError, match="not configured") as error:
        AdminAuthPolicy().validate_mutation(token="secret", origin=None, host="127.0.0.1")

    assert error.value.status == 503


def test_admin_auth_accepts_matching_token_and_same_origin() -> None:
    AdminAuthPolicy("secret").validate_mutation(
        token="secret",
        origin="http://127.0.0.1:8081",
        host="127.0.0.1:8081",
    )


def test_admin_auth_rejects_cross_origin_mutation() -> None:
    with pytest.raises(AdminAuthError, match="cross-origin") as error:
        AdminAuthPolicy("secret").validate_mutation(
            token="secret",
            origin="http://example.test",
            host="127.0.0.1:8081",
        )

    assert error.value.status == 403


def test_extract_bearer_token() -> None:
    assert extract_bearer_token("Bearer abc123") == "abc123"
    assert extract_bearer_token("Basic abc123") is None
