"""Mutation authentication helpers for the admin portal."""

from __future__ import annotations

import hmac
import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse


@dataclass(frozen=True)
class AdminSession:
    """Authenticated browser session with CSRF token."""

    session_id: str
    csrf_token: str
    created_at: str
    expires_at: str


class SessionStore:
    """In-memory session store with expiration."""

    def __init__(self, *, session_ttl_seconds: int = 3600, max_sessions: int = 10) -> None:
        self._sessions: dict[str, AdminSession] = {}
        self._expires_at: dict[str, float] = {}
        self._ttl = session_ttl_seconds
        self._max = max_sessions

    def create_session(self) -> AdminSession:
        """Create a new session with CSRF token."""
        self._evict_if_needed()
        now = time.time()
        session = AdminSession(
            session_id=secrets.token_urlsafe(32),
            csrf_token=secrets.token_urlsafe(32),
            created_at=_ts_to_iso(now),
            expires_at=_ts_to_iso(now + self._ttl),
        )
        self._sessions[session.session_id] = session
        self._expires_at[session.session_id] = now + self._ttl
        return session

    def get_session(self, session_id: str) -> AdminSession | None:
        """Return session if valid (not expired), else None."""
        expiry = self._expires_at.get(session_id)
        if expiry is None or time.time() > expiry:
            return None
        return self._sessions.get(session_id)

    def validate_csrf(self, session_id: str, csrf_token: str) -> bool:
        """Validate CSRF token matches the session's token."""
        session = self.get_session(session_id)
        if session is None:
            return False
        return hmac.compare_digest(session.csrf_token, csrf_token)

    def destroy_session(self, session_id: str) -> None:
        """Remove a session."""
        self._sessions.pop(session_id, None)
        self._expires_at.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """Remove expired sessions, return count removed."""
        now = time.time()
        expired = [sid for sid, exp in self._expires_at.items() if now > exp]
        for sid in expired:
            self.destroy_session(sid)
        return len(expired)

    def _evict_if_needed(self) -> None:
        self.cleanup_expired()
        if len(self._sessions) < self._max:
            return
        oldest_id = min(self._expires_at, key=self._expires_at.__getitem__)
        self.destroy_session(oldest_id)


@dataclass(frozen=True)
class AdminAuthPolicy:
    """Token policy used to guard admin mutation routes."""

    token: str | None = None

    @classmethod
    def from_environment(cls) -> AdminAuthPolicy:
        token = os.getenv("INKPI_ADMIN_TOKEN", "").strip() or None
        return cls(token=token)

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def validate_mutation(
        self,
        *,
        token: str | None,
        origin: str | None,
        host: str | None,
        session_id: str | None = None,
        csrf_token: str | None = None,
        sessions: SessionStore | None = None,
    ) -> None:
        # Session-based auth takes priority when all pieces are present
        if sessions is not None and session_id is not None and csrf_token is not None:
            if not sessions.validate_csrf(session_id, csrf_token):
                raise AdminAuthError("invalid or expired session", status=401)
            if origin and host and not _same_origin_host(origin, host):
                raise AdminAuthError("cross-origin mutation rejected", status=403)
            return

        # Fall back to token-based auth
        if not self.token:
            raise AdminAuthError("admin token is not configured", status=503)
        if not token or not hmac.compare_digest(token, self.token):
            raise AdminAuthError("invalid admin token", status=401)
        if origin and host and not _same_origin_host(origin, host):
            raise AdminAuthError("cross-origin mutation rejected", status=403)

    def create_session_from_token(
        self,
        token: str,
        sessions: SessionStore,
    ) -> AdminSession:
        """Validate token and create a browser session."""
        self.validate_mutation(token=token, origin=None, host=None)
        return sessions.create_session()

    def issue_browser_session(self, token: str, *, remember: bool) -> tuple[str, str, int]:
        """Return a signed, restart-safe session cookie, CSRF token, and lifetime."""
        self.validate_mutation(token=token, origin=None, host=None)
        if self.token is None:  # pragma: no cover - guarded by validation
            raise AdminAuthError("admin token is not configured", status=503)
        lifetime = 30 * 24 * 3600 if remember else 12 * 3600
        csrf_token = secrets.token_urlsafe(24)
        payload = f"{int(time.time()) + lifetime}:{csrf_token}:{secrets.token_urlsafe(18)}"
        encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        signature = hmac.new(self.token.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}", csrf_token, lifetime

    def validate_browser_session(self, cookie: str | None, csrf_token: str | None = None) -> str:
        """Validate a signed browser cookie and optionally its CSRF token."""
        if not self.token or not cookie:
            raise AdminAuthError("login required", status=401)
        encoded, separator, signature = cookie.partition(".")
        expected = hmac.new(self.token.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not separator or not hmac.compare_digest(signature, expected):
            raise AdminAuthError("invalid or expired session", status=401)
        try:
            padding = "=" * (-len(encoded) % 4)
            expires, stored_csrf, _ = base64.urlsafe_b64decode(encoded + padding).decode().split(":", 2)
        except (ValueError, UnicodeDecodeError):
            raise AdminAuthError("invalid or expired session", status=401) from None
        if int(expires) < int(time.time()):
            raise AdminAuthError("invalid or expired session", status=401)
        if csrf_token is not None and not hmac.compare_digest(stored_csrf, csrf_token):
            raise AdminAuthError("invalid CSRF token", status=403)
        return stored_csrf

    def validate_origin(self, origin: str | None, host: str | None) -> None:
        if origin and host and not _same_origin_host(origin, host):
            raise AdminAuthError("cross-origin mutation rejected", status=403)


class AdminAuthError(ValueError):
    """Raised when an admin mutation request is not authorized."""

    def __init__(self, message: str, *, status: int) -> None:
        super().__init__(message)
        self.status = status


def extract_bearer_token(value: str | None) -> str | None:
    """Extract a bearer token from an Authorization header."""

    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _same_origin_host(origin: str, host: str) -> bool:
    parsed = urlparse(origin)
    return bool(parsed.netloc) and parsed.netloc.lower() == host.lower()


def _ts_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")
