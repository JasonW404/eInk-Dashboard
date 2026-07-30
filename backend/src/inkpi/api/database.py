"""SQLite engine and request-scoped session helpers for the InkPi API."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def default_database_url() -> str:
    """Return the configured SQLite URL, rooted in the user's data directory."""

    configured = os.getenv("INKPI_DATABASE_URL")
    if configured:
        return configured
    path = Path("~/.local/share/inkpi/inkpi.db").expanduser()
    return f"sqlite+pysqlite:///{path}"


def build_engine(database_url: str | None = None) -> Engine:
    """Create an engine and ensure a file-backed SQLite parent exists."""

    url = database_url or default_database_url()
    prefix = "sqlite+pysqlite:///"
    database_file: Path | None = None
    if url.startswith(prefix):
        database_path = url.removeprefix(prefix)
        if database_path and database_path != ":memory:":
            database_file = Path(database_path).expanduser()
            database_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url)
    if database_file is not None:
        @event.listens_for(engine, "connect")
        def protect_database_file(*_: object) -> None:
            database_file.chmod(0o600)
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the shared factory used to create one session per request."""

    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    """Yield one database session for the current HTTP request."""

    with request.app.state.session_factory() as session:
        yield session
