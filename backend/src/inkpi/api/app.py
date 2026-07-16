"""FastAPI application exposing InkPi's persistent device state."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import secrets
import socket
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from inkpi.network.auth import AdminAuthError, AdminAuthPolicy, extract_bearer_token
from inkpi.network.helper_client import DEFAULT_HELPER_SOCKET, HelperClient
from inkpi.network.operations import NetworkHelper, build_operation_request
from inkpi.api import repository
from inkpi.api.database import build_engine, build_session_factory, get_session
from inkpi.api.display_renderer import (
    DisplayImageRenderer,
    DisplayRenderError,
    PlaywrightDisplayRenderer,
)
from inkpi.api.models import Agent, Base
from inkpi.api.network_status import connected_hotspot_clients
from inkpi.api.schemas import (
    AgentCredentials,
    AgentHeartbeat,
    AgentRegistration,
    DisplayRevision,
    DisplayContextRead,
    DisplayRefreshReport,
    HotspotRead,
    HotspotUpdate,
    ReportCreate,
    ReportRead,
    SystemInfoRead,
    TodoCreate,
    TodoOrder,
    TodoRead,
    TodoUpdate,
)

SessionDependency = Annotated[Session, Depends(get_session)]


def create_app(
    database_url: str | None = None,
    web_dist: str | Path | None = None,
    display_renderer: DisplayImageRenderer | None = None,
    render_base_url: str | None = None,
    network_helper: NetworkHelper | None = None,
    admin_auth: AdminAuthPolicy | None = None,
    hotspot_client_counter: Callable[[], int] | None = None,
) -> FastAPI:
    """Build an isolated API application for production or tests."""

    engine = build_engine(database_url)
    session_factory = build_session_factory(engine)
    renderer = display_renderer or PlaywrightDisplayRenderer(
        render_base_url or os.getenv("INKPI_RENDER_BASE_URL", "http://127.0.0.1:8080")
    )
    helper = network_helper or HelperClient(os.getenv("INKPI_NETWORK_HELPER_SOCKET", DEFAULT_HELPER_SOCKET))
    auth_policy = admin_auth or AdminAuthPolicy.from_environment()
    client_counter = hotspot_client_counter or connected_hotspot_clients
    hotspot_password = os.getenv("INKPI_HOTSPOT_PASSWORD")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(engine)
        repository.initialize_schema(session_factory)
        app.state.session_factory = session_factory
        yield
        renderer.close()
        engine.dispose()

    app = FastAPI(title="InkPi API", version="1.0", lifespan=lifespan)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/todos", response_model=list[TodoRead])
    def todos(session: SessionDependency) -> list[object]:
        return repository.list_todos(session)

    @app.post("/api/todos", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
    def create_todo(payload: TodoCreate, session: SessionDependency) -> object:
        with session.begin():
            return repository.create_todo(session, payload)

    @app.patch("/api/todos/{todo_id}", response_model=TodoRead)
    def update_todo(todo_id: int, payload: TodoUpdate, session: SessionDependency) -> object:
        with session.begin():
            todo = repository.get_todo(session, todo_id)
            if todo is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
            return repository.update_todo(session, todo, payload)

    @app.delete("/api/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_todo(todo_id: int, session: SessionDependency) -> Response:
        with session.begin():
            todo = repository.get_todo(session, todo_id)
            if todo is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
            repository.delete_todo(session, todo)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.put("/api/todos/order", response_model=list[TodoRead])
    def reorder_todos(payload: TodoOrder, session: SessionDependency) -> list[object]:
        try:
            with session.begin():
                return repository.reorder_todos(session, payload.ordered_ids)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    @app.get("/api/display/revision", response_model=DisplayRevision)
    def display_revision(session: SessionDependency) -> object:
        return repository.get_display_state(session)

    @app.get("/api/display/context", response_model=DisplayContextRead)
    def display_context(request: Request, session: SessionDependency) -> DisplayContextRead:
        """Return render-only facts, including an ephemeral hotspot QR payload."""

        client_host = request.client.host if request.client else ""
        if client_host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="display context is local-only",
            )
        settings = repository.get_hotspot_settings(session)
        qr_payload = None
        if settings.enabled and hotspot_password:
            qr_payload = _wifi_qr_payload(settings.ssid, hotspot_password)
        return DisplayContextRead(
            hotspot_enabled=settings.enabled,
            hotspot_ssid=settings.ssid if settings.enabled else None,
            wifi_qr_payload=qr_payload,
        )

    @app.post("/api/display/refresh", status_code=status.HTTP_204_NO_CONTENT)
    def report_display_refresh(
        payload: DisplayRefreshReport,
        request: Request,
        session: SessionDependency,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        configured_token = os.getenv("INKPI_DISPLAY_TOKEN")
        client_host = request.client.host if request.client else ""
        supplied_token = extract_bearer_token(authorization)
        if configured_token:
            if not supplied_token or not secrets.compare_digest(supplied_token, configured_token):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid display token")
        elif client_host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="remote display telemetry requires INKPI_DISPLAY_TOKEN",
            )
        current_revision = repository.get_display_state(session).revision
        if payload.revision != current_revision:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale display revision")
        repository.record_display_refresh(
            session,
            action=payload.action,
            accepted=payload.accepted,
        )
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/display/image", response_class=Response)
    def display_image(session: SessionDependency) -> Response:
        revision = repository.get_display_state(session).revision
        try:
            png = renderer.render_png(revision)
        except DisplayRenderError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        return Response(
            content=png,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "ETag": f'"inkpi-{revision}"',
                "X-InkPi-Revision": str(revision),
            },
        )

    @app.get("/api/settings/network", response_model=HotspotRead)
    def network_settings(session: SessionDependency) -> HotspotRead:
        settings = repository.get_hotspot_settings(session)
        return HotspotRead(
            enabled=settings.enabled,
            ssid=settings.ssid,
            connected_clients=client_counter(),
            updated_at=settings.updated_at,
        )

    @app.get("/api/settings/system", response_model=SystemInfoRead)
    def system_settings(session: SessionDependency) -> SystemInfoRead:
        state = repository.get_display_state(session)
        return SystemInfoRead(
            device_name=socket.gethostname(),
            firmware_version=_package_version(),
            uptime_seconds=_device_uptime_seconds(),
            display_revision=state.revision,
            last_refresh=state.last_refresh,
        )

    @app.put("/api/settings/network/hotspot", response_model=HotspotRead)
    def update_hotspot(
        payload: HotspotUpdate,
        request: Request,
        session: SessionDependency,
        authorization: Annotated[str | None, Header()] = None,
        x_admin_token: Annotated[str | None, Header()] = None,
        origin: Annotated[str | None, Header()] = None,
    ) -> HotspotRead:
        nonlocal hotspot_password
        try:
            auth_policy.validate_mutation(
                token=x_admin_token or extract_bearer_token(authorization),
                origin=origin,
                host=request.headers.get("host"),
            )
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error

        current = repository.get_hotspot_settings(session)
        if payload.enabled and not payload.password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="password is required when enabling or updating the hotspot",
            )
        action = "hotspot_disable"
        operation_payload: dict[str, object] = {}
        if payload.enabled:
            action = "hotspot_configure" if current.enabled else "hotspot_enable"
            operation_payload = {
                "ssid": payload.ssid,
                "password": payload.password,
                "mode": "visible",
            }
            hotspot_password = payload.password
        operation = helper.submit(build_operation_request(action, operation_payload))
        if operation.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=operation.message,
            )
        saved = repository.update_hotspot_settings(
            session,
            enabled=payload.enabled,
            ssid=payload.ssid,
        )
        session.commit()
        return HotspotRead(
            enabled=saved.enabled,
            ssid=saved.ssid,
            connected_clients=client_counter(),
            updated_at=saved.updated_at,
            operation=operation.to_payload(),
        )

    @app.post("/api/agents/register", response_model=AgentCredentials, status_code=status.HTTP_201_CREATED)
    def register_agent(
        payload: AgentRegistration,
        request: Request,
        session: SessionDependency,
    ) -> AgentCredentials:
        configured_token = os.getenv("INKPI_AGENT_ENROLLMENT_TOKEN")
        client_host = request.client.host if request.client else ""
        if configured_token:
            if not payload.enrollment_token or not secrets.compare_digest(payload.enrollment_token, configured_token):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid enrollment token")
        elif client_host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="remote enrollment requires INKPI_AGENT_ENROLLMENT_TOKEN",
            )

        token = secrets.token_urlsafe(32)
        with session.begin():
            agent = repository.register_agent(session, payload.name, token)
            return AgentCredentials(id=agent.id, name=agent.name, token=token)

    def authenticated_agent(
        agent_id: int,
        session: Session,
        authorization: str | None,
    ) -> Agent:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="agent bearer token required")
        agent = repository.authenticate_agent(session, agent_id, token)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid agent token")
        return agent

    @app.post("/api/agents/{agent_id}/heartbeat", response_model=AgentHeartbeat)
    def agent_heartbeat(
        agent_id: int,
        session: SessionDependency,
        authorization: Annotated[str | None, Header()] = None,
    ) -> AgentHeartbeat:
        with session.begin():
            agent = authenticated_agent(agent_id, session, authorization)
            repository.heartbeat_agent(session, agent)
            return AgentHeartbeat(id=agent.id, name=agent.name, last_seen=agent.last_seen)

    @app.post("/api/agents/{agent_id}/reports", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
    def agent_report(
        agent_id: int,
        payload: ReportCreate,
        session: SessionDependency,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ReportRead:
        with session.begin():
            agent = authenticated_agent(agent_id, session, authorization)
            report = repository.create_report(
                session,
                agent,
                payload.type,
                payload.payload,
                payload.ttl_seconds,
            )
            return ReportRead(
                id=report.id,
                agent_id=agent.id,
                agent_name=agent.name,
                type=report.type,
                payload=report.payload,
                created_at=report.created_at,
                expires_at=report.expires_at,
            )

    @app.get("/api/reports/latest", response_model=list[ReportRead])
    def reports_latest(session: SessionDependency) -> list[ReportRead]:
        return [
            ReportRead(
                id=report.id,
                agent_id=report.agent_id,
                agent_name=report.agent.name,
                type=report.type,
                payload=report.payload,
                created_at=report.created_at,
                expires_at=report.expires_at,
            )
            for report in repository.latest_reports(session)
        ]

    repository_root = Path(__file__).parents[4]
    static_root = Path(web_dist) if web_dist else repository_root / "frontend" / "dist"
    if static_root.is_dir():
        assets = static_root / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

        @app.get("/", include_in_schema=False)
        @app.get("/todo", include_in_schema=False)
        @app.get("/settings", include_in_schema=False)
        def web_application() -> FileResponse:
            return FileResponse(static_root / "index.html")

        @app.get("/eink.html", include_in_schema=False)
        def eink_application() -> FileResponse:
            return FileResponse(static_root / "eink.html")

    return app


def _device_uptime_seconds() -> float:
    try:
        return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def _package_version() -> str:
    try:
        return version("inkpi")
    except PackageNotFoundError:
        return "development"


def _wifi_qr_payload(ssid: str, password: str) -> str:
    """Build a standards-compatible WPA Wi-Fi QR payload."""

    def escaped(value: str) -> str:
        for character in ("\\", ";", ",", ":"):
            value = value.replace(character, f"\\{character}")
        return value

    return f"WIFI:T:WPA;S:{escaped(ssid)};P:{escaped(password)};;"
