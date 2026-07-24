from __future__ import annotations

import pytest

from inkpi.admin.auth import (
    AdminAuthError,
    AdminAuthPolicy,
    AdminSession,
    SessionStore,
)
from inkpi.admin.events import AdminEventLog


def test_create_session_returns_valid_session() -> None:
    store = SessionStore()
    session = store.create_session()
    assert isinstance(session, AdminSession)
    assert session.session_id
    assert session.csrf_token
    assert session.created_at
    assert session.expires_at
    assert session.session_id != session.csrf_token


def test_get_session_returns_session_before_expiry() -> None:
    store = SessionStore(session_ttl_seconds=3600)
    session = store.create_session()
    result = store.get_session(session.session_id)
    assert result is not None
    assert result.session_id == session.session_id


def test_get_session_returns_none_after_expiry() -> None:
    store = SessionStore(session_ttl_seconds=-1)
    session = store.create_session()
    assert store.get_session(session.session_id) is None


def test_validate_csrf_with_correct_token() -> None:
    store = SessionStore()
    session = store.create_session()
    assert store.validate_csrf(session.session_id, session.csrf_token) is True


def test_validate_csrf_with_wrong_token() -> None:
    store = SessionStore()
    session = store.create_session()
    assert store.validate_csrf(session.session_id, "wrong-token") is False


def test_destroy_session_removes_session() -> None:
    store = SessionStore()
    session = store.create_session()
    store.destroy_session(session.session_id)
    assert store.get_session(session.session_id) is None
    assert store.validate_csrf(session.session_id, session.csrf_token) is False


def test_cleanup_expired_removes_old_sessions() -> None:
    store = SessionStore(session_ttl_seconds=3600)
    s1 = store.create_session()
    s2 = store.create_session()
    store._expires_at[s1.session_id] = 0.0
    store._expires_at[s2.session_id] = 0.0
    removed = store.cleanup_expired()
    assert removed == 2


def test_max_sessions_evicts_oldest() -> None:
    store = SessionStore(max_sessions=2)
    s1 = store.create_session()
    s2 = store.create_session()
    s3 = store.create_session()
    assert store.get_session(s1.session_id) is None
    assert store.get_session(s2.session_id) is not None
    assert store.get_session(s3.session_id) is not None


def test_validate_mutation_with_valid_session_and_csrf() -> None:
    policy = AdminAuthPolicy(token="secret")
    store = SessionStore()
    session = store.create_session()
    policy.validate_mutation(
        token=None,
        origin=None,
        host=None,
        session_id=session.session_id,
        csrf_token=session.csrf_token,
        sessions=store,
    )


def test_validate_mutation_with_invalid_session_raises() -> None:
    policy = AdminAuthPolicy(token="secret")
    store = SessionStore()
    with pytest.raises(AdminAuthError, match="invalid or expired session"):
        policy.validate_mutation(
            token=None,
            origin=None,
            host=None,
            session_id="bad-session",
            csrf_token="bad-csrf",
            sessions=store,
        )


def test_validate_mutation_falls_back_to_token_when_no_session() -> None:
    policy = AdminAuthPolicy(token="secret")
    policy.validate_mutation(token="secret", origin=None, host=None)


def test_create_session_from_valid_token() -> None:
    policy = AdminAuthPolicy(token="secret")
    store = SessionStore()
    session = policy.create_session_from_token("secret", store)
    assert isinstance(session, AdminSession)
    assert store.get_session(session.session_id) is not None


def test_create_session_from_invalid_token_raises() -> None:
    policy = AdminAuthPolicy(token="secret")
    store = SessionStore()
    with pytest.raises(AdminAuthError, match="invalid admin token"):
        policy.create_session_from_token("wrong", store)


def test_session_id_and_csrf_redacted_in_event_log() -> None:
    log = AdminEventLog()
    event = log.record(
        source="session",
        message="login",
        details={"session_id": "abc123", "csrf": "xyz789", "user": "admin"},
    )
    assert event.details["session_id"] == "[redacted]"
    assert event.details["csrf"] == "[redacted]"
    assert event.details["user"] == "admin"
