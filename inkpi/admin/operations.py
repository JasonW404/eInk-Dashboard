"""Admin network operation contracts and local in-memory helper."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

NetworkOperationAction = Literal[
    "wifi_scan",
    "wifi_connect",
    "wifi_forget",
    "hotspot_enable",
    "hotspot_disable",
    "hotspot_rotate_password",
    "policy_reconcile",
]

OperationStatus = Literal["queued", "running", "succeeded", "failed"]


@dataclass(frozen=True)
class NetworkOperationRequest:
    """Allowlisted network mutation request from the admin portal."""

    action: NetworkOperationAction
    ssid: str | None = None
    password_supplied: bool = False
    hidden_ssid: bool = False
    hotspot_mode: Literal["visible", "hidden"] | None = None
    share_upstream: bool = False


@dataclass(frozen=False)
class NetworkOperation:
    """Trackable helper operation returned to portal callers."""

    operation_id: str
    action: NetworkOperationAction
    status: OperationStatus
    created_at: str
    message: str
    safe_details: dict[str, object] = field(default_factory=dict)

    def to_payload(self) -> dict:
        return asdict(self)

    def update_status(self, status: OperationStatus, message: str = "") -> None:
        self.status = status
        if message:
            self.message = message


class NetworkHelper(Protocol):
    """Narrow privileged-helper boundary consumed by `inkpi-admin`."""

    def submit(self, request: NetworkOperationRequest) -> NetworkOperation: ...

    def get_operation(self, operation_id: str) -> NetworkOperation | None: ...

    def list_operations(self) -> list[NetworkOperation]: ...


class InMemoryNetworkHelper:
    """Local fake helper used until the real privileged helper is wired.

    It records safe operation metadata and returns deterministic queued
    operations. It intentionally never receives or stores Wi-Fi passwords.
    """

    def __init__(self) -> None:
        self._operations: dict[str, NetworkOperation] = {}

    def submit(self, request: NetworkOperationRequest) -> NetworkOperation:
        operation = NetworkOperation(
            operation_id=str(uuid4()),
            action=request.action,
            status="queued",
            created_at=_now(),
            message=_message_for(request),
            safe_details=_safe_details(request),
        )
        self._operations[operation.operation_id] = operation
        return operation

    def get_operation(self, operation_id: str) -> NetworkOperation | None:
        return self._operations.get(operation_id)

    def list_operations(self) -> list[NetworkOperation]:
        return list(self._operations.values())

    def complete_operation(
        self,
        operation_id: str,
        status: OperationStatus,
        message: str = "",
    ) -> NetworkOperation | None:
        operation = self._operations.get(operation_id)
        if operation is not None:
            operation.update_status(status, message)
        return operation


def build_operation_request(
    action: NetworkOperationAction,
    payload: dict[str, object],
) -> NetworkOperationRequest:
    """Validate a request payload into the helper's allowlisted operation type."""

    if action == "wifi_scan":
        return NetworkOperationRequest(action=action)

    if action == "wifi_connect":
        ssid = _required_text(payload, "ssid")
        return NetworkOperationRequest(
            action=action,
            ssid=ssid,
            password_supplied=bool(payload.get("password")),
            hidden_ssid=bool(payload.get("hidden_ssid", False)),
        )

    if action == "wifi_forget":
        return NetworkOperationRequest(action=action, ssid=_required_text(payload, "ssid"))

    if action == "hotspot_enable":
        mode = str(payload.get("mode", "visible"))
        if mode not in {"visible", "hidden"}:
            raise ValueError("hotspot mode must be visible or hidden")
        return NetworkOperationRequest(
            action=action,
            hotspot_mode=mode,  # type: ignore[arg-type]
            share_upstream=bool(payload.get("share_upstream", False)),
        )

    if action in {"hotspot_disable", "hotspot_rotate_password", "policy_reconcile"}:
        return NetworkOperationRequest(action=action)

    raise ValueError(f"unsupported network operation: {action}")


def _required_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _message_for(request: NetworkOperationRequest) -> str:
    if request.action == "wifi_scan":
        return "Wi-Fi scan queued"
    if request.action == "wifi_connect":
        return f"Wi-Fi connection queued for {request.ssid}"
    if request.action == "wifi_forget":
        return f"Wi-Fi forget queued for {request.ssid}"
    if request.action == "hotspot_enable":
        return f"Hotspot enable queued in {request.hotspot_mode} mode"
    if request.action == "hotspot_disable":
        return "Hotspot disable queued"
    if request.action == "hotspot_rotate_password":
        return "Hotspot password rotation queued"
    return "Network policy reconciliation queued"


def _safe_details(request: NetworkOperationRequest) -> dict[str, object]:
    details: dict[str, object] = {}
    if request.ssid:
        details["ssid"] = request.ssid
    if request.password_supplied:
        details["password_supplied"] = True
    if request.hidden_ssid:
        details["hidden_ssid"] = True
    if request.hotspot_mode:
        details["hotspot_mode"] = request.hotspot_mode
    if request.share_upstream:
        details["share_upstream"] = True
    return details


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
