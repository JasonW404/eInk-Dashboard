"""Persistent models owned by the Raspberry Pi API."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_full_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HotspotSettings(Base):
    __tablename__ = "hotspot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ssid: Mapped[str] = mapped_column(String(32), nullable=False, default="InkPi-AP")
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
