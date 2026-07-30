"""Persistent models owned by the Raspberry Pi API."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("todos.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_on_eink: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class DisplayState(Base):
    __tablename__ = "display_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    revision: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid4()))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_full_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dashboard_sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dashboard_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    todo_show_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    todo_sort: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    dashboard_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HotspotSettings(Base):
    __tablename__ = "hotspot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    desired_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ssid: Mapped[str] = mapped_column(String(32), nullable=False, default="InkPi-AP")
    security: Mapped[str] = mapped_column(String(16), nullable=False, default="wpa2")
    password: Mapped[str] = mapped_column(Text, nullable=False, default="")
    connected_clients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    operation_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    network_last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class NetworkCommand(Base):
    __tablename__ = "network_commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class IntegrationSettings(Base):
    __tablename__ = "integration_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    github_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    github_username: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    github_organization: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    github_commit_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    github_extra_repos: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    github_token: Mapped[str] = mapped_column(Text, nullable=False, default="")
    codex_source: Mapped[str] = mapped_column(String(32), nullable=False, default="host-agent")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class DisplayPage(Base):
    __tablename__ = "display_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="photo")
    file_name: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    reports: Mapped[list[Report]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    agent: Mapped[Agent] = relationship(back_populates="reports")
