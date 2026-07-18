"""FastAPI application exposing InkPi's persistent device state."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
import io
import os
from pathlib import Path
import secrets
import socket
import time
from typing import Annotated
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from PIL import Image, ImageOps, UnidentifiedImageError

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
from inkpi.api.hotspot_status import hotspot_is_active
from inkpi.api.models import Agent, Base
from inkpi.api.network_status import connected_hotspot_clients
from inkpi.api.schemas import (
    AgentCredentials,
    AgentHeartbeat,
    AgentRegistration,
    AuthSessionRead,
    DisplayRevision,
    DisplayContextRead,
    DisplayRefreshReport,
    HotspotRead,
    HotspotCredentialsRead,
    HotspotUpdate,
    LoginRequest,
    ReportCreate,
    ReportRead,
    SystemInfoRead,
    TodoCreate,
    TodoOrder,
    TodoDisplaySettings,
    TodoRead,
    TodoUpdate,
    PageOrder,
    PageRead,
    PageUpdate,
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
    hotspot_active_checker: Callable[[], bool] | None = None,
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
    active_checker = hotspot_active_checker or hotspot_is_active
    upload_root = Path(os.getenv("INKPI_UPLOAD_DIR", Path("~/.local/share/inkpi/pages").expanduser()))
    upload_root.mkdir(parents=True, exist_ok=True)

    def current_hotspot_password() -> str | None:
        return helper.get_hotspot_password() or os.getenv("INKPI_HOTSPOT_PASSWORD")

    def scheduled_page(session: Session) -> object | None:
        pages = [page for page in repository.list_pages(session) if page.enabled]
        if not pages:
            return None
        state = repository.get_display_state(session)
        entries: list[tuple[object | None, int, int]] = [
            (None, state.dashboard_interval_seconds, state.dashboard_sort_order),
            *[(page, page.interval_seconds, page.sort_order) for page in pages],
        ]
        entries.sort(key=lambda item: item[2])
        cursor = int(time.time()) % sum(duration for _, duration, _ in entries)
        for page, duration, _ in entries:
            if cursor < duration:
                return page
            cursor -= duration
        return None

    def effective_revision(session: Session) -> str:
        base = repository.get_display_state(session).revision
        page = scheduled_page(session)
        if page is None and not any(item.enabled for item in repository.list_pages(session)):
            return base
        return str(uuid5(NAMESPACE_URL, f"{base}:page:{getattr(page, 'id', 'dashboard')}"))

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

    @app.post("/api/auth/login", response_model=AuthSessionRead)
    def login(
        payload: LoginRequest,
        request: Request,
        response: Response,
        origin: Annotated[str | None, Header()] = None,
    ) -> AuthSessionRead:
        try:
            auth_policy.validate_mutation(
                token=payload.token,
                origin=origin,
                host=request.headers.get("host"),
            )
            cookie, csrf_token, lifetime = auth_policy.issue_browser_session(payload.token, remember=payload.remember)
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        response.set_cookie(
            "inkpi_admin_session",
            cookie,
            max_age=lifetime if payload.remember else None,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/",
        )
        return AuthSessionRead(authenticated=True, csrf_token=csrf_token)

    @app.get("/api/auth/session", response_model=AuthSessionRead)
    def auth_session(inkpi_admin_session: Annotated[str | None, Cookie()] = None) -> AuthSessionRead:
        try:
            csrf_token = auth_policy.validate_browser_session(inkpi_admin_session)
        except AdminAuthError:
            return AuthSessionRead(authenticated=False)
        return AuthSessionRead(authenticated=True, csrf_token=csrf_token)

    @app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(response: Response) -> Response:
        response.delete_cookie("inkpi_admin_session", path="/", samesite="strict")
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response.headers)

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

    @app.get("/api/settings/todos/display", response_model=TodoDisplaySettings)
    def todo_display_settings(session: SessionDependency) -> TodoDisplaySettings:
        state = repository.get_display_state(session)
        return TodoDisplaySettings(show_completed=state.todo_show_completed, sort=state.todo_sort)

    @app.put("/api/settings/todos/display", response_model=TodoDisplaySettings)
    def update_todo_display_settings(
        payload: TodoDisplaySettings, session: SessionDependency
    ) -> TodoDisplaySettings:
        with session.begin():
            state = repository.update_todo_display_settings(
                session, show_completed=payload.show_completed, sort=payload.sort
            )
        return TodoDisplaySettings(show_completed=state.todo_show_completed, sort=state.todo_sort)

    @app.get("/api/display/revision", response_model=DisplayRevision)
    def display_revision(session: SessionDependency) -> object:
        state = repository.get_display_state(session)
        return DisplayRevision(revision=effective_revision(session), updated_at=state.updated_at)

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
        hotspot_active = active_checker()
        qr_payload = None
        hotspot_password = current_hotspot_password()
        if hotspot_active and (settings.security == "open" or hotspot_password):
            qr_payload = _wifi_qr_payload(settings.ssid, hotspot_password, settings.security)
        return DisplayContextRead(
            hotspot_enabled=hotspot_active,
            hotspot_ssid=settings.ssid if hotspot_active else None,
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
        current_revision = effective_revision(session)
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
        revision = effective_revision(session)
        page = scheduled_page(session)
        if page is not None:
            image_path = upload_root / page.file_name
            if not image_path.is_file():
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="scheduled page image is missing")
            return FileResponse(
                image_path,
                media_type="image/png",
                headers={"Cache-Control": "no-store", "ETag": f'"inkpi-{revision}"', "X-InkPi-Revision": revision},
            )
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

    @app.get("/api/display/dashboard-image", response_class=Response)
    def dashboard_image(session: SessionDependency) -> Response:
        """Render the built-in dashboard regardless of the active playlist item."""
        revision = repository.get_display_state(session).revision
        try:
            png = renderer.render_png(revision)
        except DisplayRenderError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=60"})

    @app.get("/api/settings/network", response_model=HotspotRead)
    def network_settings(session: SessionDependency) -> HotspotRead:
        settings = repository.get_hotspot_settings(session)
        return HotspotRead(
            enabled=active_checker(),
            ssid=settings.ssid,
            security=settings.security,
            connected_clients=client_counter(),
            updated_at=settings.updated_at,
        )

    @app.get("/api/settings/network/hotspot/credentials", response_model=HotspotCredentialsRead)
    def hotspot_credentials(
        response: Response,
        inkpi_admin_session: Annotated[str | None, Cookie()] = None,
    ) -> HotspotCredentialsRead:
        try:
            auth_policy.validate_browser_session(inkpi_admin_session)
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        settings = None
        with session_factory() as session:
            settings = repository.get_hotspot_settings(session)
        password = current_hotspot_password() if settings.security != "open" else None
        if settings.security != "open" and not password:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hotspot password is unavailable")
        response.headers["Cache-Control"] = "no-store"
        return HotspotCredentialsRead(password=password)

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
        x_csrf_token: Annotated[str | None, Header()] = None,
        inkpi_admin_session: Annotated[str | None, Cookie()] = None,
        origin: Annotated[str | None, Header()] = None,
    ) -> HotspotRead:
        try:
            if inkpi_admin_session:
                auth_policy.validate_browser_session(inkpi_admin_session, x_csrf_token)
                auth_policy.validate_origin(origin, request.headers.get("host"))
            else:
                auth_policy.validate_mutation(
                    token=x_admin_token or extract_bearer_token(authorization),
                    origin=origin,
                    host=request.headers.get("host"),
                )
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error

        current = repository.get_hotspot_settings(session)
        if payload.enabled and payload.security != "open" and not payload.password:
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
                "security": payload.security,
            }
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
            security=payload.security,
        )
        repository.bump_revision(session)
        session.commit()
        return HotspotRead(
            enabled=active_checker(),
            ssid=saved.ssid,
            security=saved.security,
            connected_clients=client_counter(),
            updated_at=saved.updated_at,
            operation=operation.to_payload(),
        )

    @app.get("/api/pages", response_model=list[PageRead])
    def pages(session: SessionDependency) -> list[object]:
        state = repository.get_display_state(session)
        result: list[object] = [
            {
                "id": 0, "kind": "dashboard", "name": "Dashboard",
                "sort_order": state.dashboard_sort_order,
                "interval_seconds": state.dashboard_interval_seconds,
                "enabled": True, "created_at": state.updated_at, "updated_at": state.updated_at,
            },
            *repository.list_pages(session),
        ]
        return sorted(result, key=lambda item: item["sort_order"] if isinstance(item, dict) else item.sort_order)

    @app.post("/api/pages", response_model=PageRead, status_code=status.HTTP_201_CREATED)
    async def upload_page(
        request: Request,
        session: SessionDependency,
        x_file_name: Annotated[str | None, Header()] = None,
        x_csrf_token: Annotated[str | None, Header()] = None,
        inkpi_admin_session: Annotated[str | None, Cookie()] = None,
    ) -> object:
        try:
            auth_policy.validate_browser_session(inkpi_admin_session, x_csrf_token)
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        body = await request.body()
        if not body or len(body) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="image must be between 1 byte and 15 MB")
        try:
            source = Image.open(io.BytesIO(body))
            source.load()
            source = ImageOps.exif_transpose(source).convert("RGB")
        except (UnidentifiedImageError, OSError) as error:
            raise HTTPException(status_code=415, detail="upload a valid image") from error
        canvas = ImageOps.fit(source, (800, 480), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        file_name = f"{uuid4()}.png"
        canvas.save(upload_root / file_name, format="PNG", optimize=True)
        name = Path(x_file_name or "Photo").name[:255] or "Photo"
        with session.begin():
            return repository.create_page(session, name=name, file_name=file_name)

    @app.get("/api/pages/{page_id}/image", response_class=FileResponse)
    def page_image(page_id: int, session: SessionDependency) -> FileResponse:
        page = repository.get_page(session, page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="page not found")
        image_path = upload_root / page.file_name
        if not image_path.is_file():
            raise HTTPException(status_code=404, detail="page image is missing")
        return FileResponse(image_path, media_type="image/png", headers={"Cache-Control": "private, max-age=60"})

    @app.patch("/api/pages/{page_id}", response_model=PageRead)
    def update_page(
        page_id: int, payload: PageUpdate, session: SessionDependency,
        x_csrf_token: Annotated[str | None, Header()] = None,
        inkpi_admin_session: Annotated[str | None, Cookie()] = None,
    ) -> object:
        try:
            auth_policy.validate_browser_session(inkpi_admin_session, x_csrf_token)
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        with session.begin():
            if page_id == 0:
                changes = payload.model_dump(exclude_unset=True)
                if "enabled" in changes or "name" in changes:
                    raise HTTPException(status_code=422, detail="the dashboard name and enabled state are fixed")
                state = repository.get_display_state(session)
                if payload.interval_seconds is not None:
                    state.dashboard_interval_seconds = payload.interval_seconds
                    state.updated_at = repository.utc_now()
                    repository.bump_revision(session)
                return {
                    "id": 0, "kind": "dashboard", "name": "Dashboard",
                    "sort_order": state.dashboard_sort_order,
                    "interval_seconds": state.dashboard_interval_seconds,
                    "enabled": True, "created_at": state.updated_at, "updated_at": state.updated_at,
                }
            page = repository.get_page(session, page_id)
            if page is None:
                raise HTTPException(status_code=404, detail="page not found")
            return repository.update_page(session, page, payload.model_dump(exclude_unset=True))

    @app.delete("/api/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_page(
        page_id: int, session: SessionDependency,
        x_csrf_token: Annotated[str | None, Header()] = None,
        inkpi_admin_session: Annotated[str | None, Cookie()] = None,
    ) -> Response:
        try:
            auth_policy.validate_browser_session(inkpi_admin_session, x_csrf_token)
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        with session.begin():
            page = repository.get_page(session, page_id)
            if page is None:
                raise HTTPException(status_code=404, detail="page not found")
            image_path = upload_root / page.file_name
            repository.delete_page(session, page)
        image_path.unlink(missing_ok=True)
        return Response(status_code=204)

    @app.put("/api/pages/order", response_model=list[PageRead])
    def reorder_pages(
        payload: PageOrder, session: SessionDependency,
        x_csrf_token: Annotated[str | None, Header()] = None,
        inkpi_admin_session: Annotated[str | None, Cookie()] = None,
    ) -> list[object]:
        try:
            auth_policy.validate_browser_session(inkpi_admin_session, x_csrf_token)
        except AdminAuthError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        try:
            with session.begin():
                repository.reorder_pages(session, payload.ordered_ids)
            return pages(session)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

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
        @app.get("/pages", include_in_schema=False)
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


def _wifi_qr_payload(ssid: str, password: str | None, security: str = "wpa2") -> str:
    """Build a standards-compatible WPA Wi-Fi QR payload."""

    def escaped(value: str) -> str:
        for character in ("\\", ";", ",", ":"):
            value = value.replace(character, f"\\{character}")
        return value

    if security == "open":
        return f"WIFI:T:nopass;S:{escaped(ssid)};;"
    return f"WIFI:T:WPA;S:{escaped(ssid)};P:{escaped(password or '')};;"
