"""Versioned request and response schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    completed: bool = False
    display_on_eink: bool = True

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    completed: bool | None = None
    display_on_eink: bool | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class TodoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    completed: bool
    display_on_eink: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class TodoOrder(BaseModel):
    ordered_ids: list[int] = Field(min_length=1)


class TodoDisplaySettings(BaseModel):
    show_completed: bool = True
    sort: str = Field(default="manual", pattern="^(manual|created_asc|created_desc|completed_asc|completed_desc)$")


class DisplayRevision(BaseModel):
    revision: str
    updated_at: datetime


class DisplayRefreshReport(BaseModel):
    revision: str = Field(min_length=36, max_length=36)
    action: str = Field(min_length=1, max_length=20)
    accepted: bool


class DisplayContextRead(BaseModel):
    hotspot_enabled: bool
    hotspot_ssid: str | None
    wifi_qr_payload: str | None


class SystemInfoRead(BaseModel):
    device_name: str
    firmware_version: str
    uptime_seconds: float
    display_revision: str
    last_refresh: datetime | None


class HotspotUpdate(BaseModel):
    enabled: bool
    ssid: str = Field(min_length=1, max_length=32)
    security: str = Field(default="wpa2", pattern="^(open|wpa2|wpa3|wpa2-wpa3)$")
    password: str | None = Field(default=None, max_length=63)

    @field_validator("ssid")
    @classmethod
    def ssid_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ssid must not be blank")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        if value is not None and value != "" and len(value) < 8:
            raise ValueError("password must contain 8 to 63 characters")
        return value or None


class HotspotRead(BaseModel):
    enabled: bool
    ssid: str
    security: str
    connected_clients: int
    updated_at: datetime
    operation: dict[str, object] | None = None


class HotspotCredentialsRead(BaseModel):
    password: str | None


class PageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str = "photo"
    content: str | None = None
    name: str
    sort_order: int
    interval_seconds: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class PageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    interval_seconds: int | None = Field(default=None, ge=10, le=86400)
    enabled: bool | None = None
    content: str | None = None


class TextPageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class PageOrder(BaseModel):
    ordered_ids: list[int]


class LoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=500)
    remember: bool = False


class AuthSessionRead(BaseModel):
    authenticated: bool
    csrf_token: str | None = None


class AgentRegistration(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enrollment_token: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class AgentCredentials(BaseModel):
    id: int
    name: str
    token: str


class AgentHeartbeat(BaseModel):
    id: int
    name: str
    last_seen: datetime


class ReportCreate(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    payload: dict[str, object]
    ttl_seconds: int | None = Field(default=None, ge=60, le=2_592_000)

    @field_validator("type")
    @classmethod
    def type_must_not_be_blank(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("type must not be blank")
        return value


class ReportRead(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    type: str
    payload: dict[str, object]
    created_at: datetime
    expires_at: datetime | None
