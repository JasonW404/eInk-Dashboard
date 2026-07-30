"""Transactional operations over InkPi's single persistent state store."""

from __future__ import annotations

from datetime import timedelta
import hashlib
import secrets
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from inkpi.api.models import Agent, DisplayPage, DisplayState, HotspotSettings, IntegrationSettings, NetworkCommand, Report, Todo, utc_now
from inkpi.api.schemas import TodoCreate, TodoUpdate


def initialize_schema(session_factory: sessionmaker[Session]) -> None:
    """Create the initial display revision row after metadata initialization."""

    with session_factory.begin() as session:
        display_columns = {
            row[1] for row in session.connection().exec_driver_sql("PRAGMA table_info(display_state)")
        }
        if display_columns and "dashboard_sort_order" not in display_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE display_state ADD COLUMN dashboard_sort_order INTEGER NOT NULL DEFAULT 0"
            )
        if display_columns and "dashboard_interval_seconds" not in display_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE display_state ADD COLUMN dashboard_interval_seconds INTEGER NOT NULL DEFAULT 60"
            )
        if display_columns and "todo_show_completed" not in display_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE display_state ADD COLUMN todo_show_completed BOOLEAN NOT NULL DEFAULT 1"
            )
        if display_columns and "todo_sort" not in display_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE display_state ADD COLUMN todo_sort VARCHAR(24) NOT NULL DEFAULT 'manual'"
            )
        if display_columns and "dashboard_enabled" not in display_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE display_state ADD COLUMN dashboard_enabled BOOLEAN NOT NULL DEFAULT 1"
            )
        todo_columns = {
            row[1] for row in session.connection().exec_driver_sql("PRAGMA table_info(todos)")
        }
        if todo_columns and "parent_id" not in todo_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE todos ADD COLUMN parent_id INTEGER REFERENCES todos(id)"
            )
            session.connection().exec_driver_sql(
                "CREATE INDEX ix_todos_parent_id ON todos (parent_id)"
            )
        hotspot_columns = {
            row[1] for row in session.connection().exec_driver_sql("PRAGMA table_info(hotspot_settings)")
        }
        if hotspot_columns and "security" not in hotspot_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE hotspot_settings ADD COLUMN security VARCHAR(16) NOT NULL DEFAULT 'wpa2'"
            )
        for name, definition in (
            ("desired_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
            ("password", "TEXT NOT NULL DEFAULT ''"),
            ("connected_clients", "INTEGER NOT NULL DEFAULT 0"),
            ("operation_status", "VARCHAR(20) NOT NULL DEFAULT 'idle'"),
            ("operation_message", "TEXT NOT NULL DEFAULT ''"),
            ("network_last_seen", "DATETIME"),
        ):
            if hotspot_columns and name not in hotspot_columns:
                session.connection().exec_driver_sql(
                    f"ALTER TABLE hotspot_settings ADD COLUMN {name} {definition}"
                )
        page_info = list(session.connection().exec_driver_sql("PRAGMA table_info(display_pages)"))
        page_columns = {row[1] for row in page_info}
        if page_columns and "kind" not in page_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE display_pages ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'photo'"
            )
        if page_columns and "content" not in page_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE display_pages ADD COLUMN content TEXT"
            )
        page_info = list(session.connection().exec_driver_sql("PRAGMA table_info(display_pages)"))
        file_name_row = next((row for row in page_info if row[1] == "file_name"), None)
        if file_name_row is not None and file_name_row[3] == 1:
            conn = session.connection()
            conn.exec_driver_sql(
                "CREATE TABLE display_pages_new ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  name VARCHAR(255) NOT NULL,"
                "  kind VARCHAR(20) NOT NULL DEFAULT 'photo',"
                "  file_name VARCHAR(255) UNIQUE,"
                "  content TEXT,"
                "  sort_order INTEGER NOT NULL,"
                "  interval_seconds INTEGER NOT NULL DEFAULT 60,"
                "  enabled BOOLEAN NOT NULL DEFAULT 1,"
                "  created_at DATETIME NOT NULL,"
                "  updated_at DATETIME NOT NULL"
                ")"
            )
            conn.exec_driver_sql(
                "INSERT INTO display_pages_new"
                " (id, name, kind, file_name, content, sort_order, interval_seconds, enabled, created_at, updated_at)"
                " SELECT id, name, kind, file_name, content, sort_order, interval_seconds, enabled, created_at, updated_at"
                " FROM display_pages"
            )
            conn.exec_driver_sql("DROP TABLE display_pages")
            conn.exec_driver_sql("ALTER TABLE display_pages_new RENAME TO display_pages")
            conn.exec_driver_sql("CREATE INDEX ix_display_pages_sort_order ON display_pages (sort_order)")
        if session.get(DisplayState, 1) is None:
            session.add(DisplayState(id=1))
        else:
            state = get_display_state(session)
            if not isinstance(state.revision, str) or len(state.revision) != 36:
                state.revision = str(uuid4())
        if session.get(HotspotSettings, 1) is None:
            session.add(HotspotSettings(id=1))
        if session.get(IntegrationSettings, 1) is None:
            session.add(IntegrationSettings(id=1))


def list_todos(session: Session) -> list[Todo]:
    return list(session.scalars(select(Todo).order_by(Todo.sort_order, Todo.id)))


def get_integration_settings(session: Session) -> IntegrationSettings:
    settings = session.get(IntegrationSettings, 1)
    if settings is None:
        settings = IntegrationSettings(id=1)
        session.add(settings)
        session.flush()
    return settings


def queue_network_command(
    session: Session,
    action: str,
    payload: dict[str, object],
) -> NetworkCommand:
    session.execute(
        update(NetworkCommand)
        .where(NetworkCommand.status.in_(("queued", "running")))
        .values(status="superseded", payload={}, updated_at=utc_now())
    )
    command = NetworkCommand(action=action, payload=payload)
    session.add(command)
    session.flush()
    return command


def claim_network_command(session: Session) -> NetworkCommand | None:
    command = session.scalar(
        select(NetworkCommand)
        .where(NetworkCommand.status == "queued")
        .order_by(NetworkCommand.id)
        .limit(1)
    )
    if command is not None:
        command.status = "running"
        command.updated_at = utc_now()
        session.flush()
    return command


def complete_network_command(
    session: Session,
    command_id: int,
    *,
    status: str,
    message: str,
    hotspot_active: bool,
    connected_clients: int,
) -> NetworkCommand | None:
    command = session.get(NetworkCommand, command_id)
    if command is None or command.status != "running":
        return None
    command.status = status
    command.message = message
    command.payload = {}
    command.updated_at = utc_now()
    settings = get_hotspot_settings(session)
    settings.enabled = hotspot_active
    settings.connected_clients = connected_clients
    settings.operation_status = status
    settings.operation_message = message
    settings.network_last_seen = utc_now()
    settings.updated_at = utc_now()
    session.flush()
    return command


def update_network_status(
    session: Session,
    *,
    hotspot_active: bool,
    connected_clients: int,
) -> HotspotSettings:
    settings = get_hotspot_settings(session)
    settings.enabled = hotspot_active
    settings.connected_clients = connected_clients
    settings.network_last_seen = utc_now()
    session.flush()
    return settings


def get_or_create_cloud_agent(session: Session) -> Agent:
    agent = session.scalar(select(Agent).where(Agent.name == "inkpi-cloud"))
    if agent is None:
        agent = Agent(name="inkpi-cloud", token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest())
        session.add(agent)
        session.flush()
    return agent


def get_todo(session: Session, todo_id: int) -> Todo | None:
    return session.get(Todo, todo_id)


def create_todo(session: Session, payload: TodoCreate) -> Todo:
    if payload.parent_id is not None:
        parent = get_todo(session, payload.parent_id)
        if parent is None:
            raise ValueError("parent todo not found")
        if parent.parent_id is not None:
            grandparent = get_todo(session, parent.parent_id)
            if grandparent is None:
                raise ValueError("parent todo hierarchy is invalid")
            if grandparent.parent_id is not None:
                raise ValueError("todos support a maximum of 3 levels")
    next_order = session.scalar(select(func.coalesce(func.max(Todo.sort_order), -1) + 1))
    todo = Todo(sort_order=int(next_order or 0), **payload.model_dump())
    session.add(todo)
    session.flush()
    bump_revision(session)
    return todo


def update_todo(session: Session, todo: Todo, payload: TodoUpdate) -> Todo:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(todo, field, value)
    todo.updated_at = utc_now()
    session.flush()
    bump_revision(session)
    return todo


def delete_todo(session: Session, todo: Todo) -> None:
    child_ids = list(session.scalars(select(Todo.id).where(Todo.parent_id == todo.id)))
    descendant_ids = list(
        session.scalars(select(Todo.id).where(Todo.parent_id.in_(child_ids)))
    ) if child_ids else []
    removed_ids = [todo.id, *child_ids, *descendant_ids]
    for item in list(session.scalars(select(Todo).where(Todo.id.in_(removed_ids)))):
        session.delete(item)
    session.flush()
    for sort_order, item in enumerate(list_todos(session)):
        item.sort_order = sort_order
    bump_revision(session)


def reorder_todos(session: Session, ordered_ids: list[int]) -> list[Todo]:
    todos = list_todos(session)
    existing_ids = [todo.id for todo in todos]
    if len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError("ordered_ids must not contain duplicates")
    if set(ordered_ids) != set(existing_ids):
        raise ValueError("ordered_ids must contain every todo exactly once")
    by_id = {todo.id: todo for todo in todos}
    for sort_order, todo_id in enumerate(ordered_ids):
        by_id[todo_id].sort_order = sort_order
        by_id[todo_id].updated_at = utc_now()
    session.flush()
    bump_revision(session)
    return [by_id[todo_id] for todo_id in ordered_ids]


def get_display_state(session: Session) -> DisplayState:
    state = session.get(DisplayState, 1)
    if state is None:
        raise RuntimeError("display state is not initialized")
    return state


def bump_revision(session: Session) -> None:
    session.execute(
        update(DisplayState)
        .where(DisplayState.id == 1)
        .values(revision=str(uuid4()), updated_at=utc_now())
    )


def record_display_refresh(
    session: Session,
    *,
    action: str,
    accepted: bool,
) -> DisplayState:
    state = get_display_state(session)
    if accepted:
        now = utc_now()
        state.last_refresh = now
        state.refresh_count += 1
        if action == "full":
            state.last_full_refresh = now
        session.flush()
    return state


def update_todo_display_settings(
    session: Session, *, show_completed: bool, sort: str
) -> DisplayState:
    state = get_display_state(session)
    state.todo_show_completed = show_completed
    state.todo_sort = sort
    state.updated_at = utc_now()
    session.flush()
    bump_revision(session)
    return state


def get_hotspot_settings(session: Session) -> HotspotSettings:
    settings = session.get(HotspotSettings, 1)
    if settings is None:
        raise RuntimeError("hotspot settings are not initialized")
    return settings


def update_hotspot_settings(
    session: Session,
    *,
    enabled: bool,
    ssid: str,
    security: str,
    password: str | None = None,
) -> HotspotSettings:
    settings = get_hotspot_settings(session)
    settings.desired_enabled = enabled
    settings.ssid = ssid
    settings.security = security
    if security == "open":
        settings.password = ""
    elif password is not None:
        settings.password = password
    settings.operation_status = "queued"
    settings.operation_message = "Waiting for Pi network service"
    settings.updated_at = utc_now()
    session.flush()
    return settings


def list_pages(session: Session) -> list[DisplayPage]:
    return list(session.scalars(select(DisplayPage).order_by(DisplayPage.sort_order, DisplayPage.id)))


def get_page(session: Session, page_id: int) -> DisplayPage | None:
    return session.get(DisplayPage, page_id)


def create_page(session: Session, *, name: str, file_name: str) -> DisplayPage:
    state = get_display_state(session)
    next_order = max(
        state.dashboard_sort_order,
        int(session.scalar(select(func.coalesce(func.max(DisplayPage.sort_order), -1))) or -1),
    ) + 1
    page = DisplayPage(name=name, file_name=file_name, sort_order=int(next_order or 0))
    session.add(page)
    session.flush()
    bump_revision(session)
    return page


def create_text_page(session: Session, *, name: str, content: str) -> DisplayPage:
    state = get_display_state(session)
    next_order = max(
        state.dashboard_sort_order,
        int(session.scalar(select(func.coalesce(func.max(DisplayPage.sort_order), -1))) or -1),
    ) + 1
    page = DisplayPage(name=name, kind="text", content=content, sort_order=int(next_order or 0))
    session.add(page)
    session.flush()
    bump_revision(session)
    return page


def update_page(session: Session, page: DisplayPage, changes: dict[str, object]) -> DisplayPage:
    for field, value in changes.items():
        setattr(page, field, value)
    page.updated_at = utc_now()
    session.flush()
    bump_revision(session)
    return page


def delete_page(session: Session, page: DisplayPage) -> None:
    removed_order = page.sort_order
    session.delete(page)
    session.flush()
    session.execute(update(DisplayPage).where(DisplayPage.sort_order > removed_order).values(sort_order=DisplayPage.sort_order - 1))
    state = get_display_state(session)
    if state.dashboard_sort_order > removed_order:
        state.dashboard_sort_order -= 1
    bump_revision(session)


def reorder_pages(session: Session, ordered_ids: list[int]) -> list[DisplayPage]:
    pages = list_pages(session)
    if len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != {0, *[page.id for page in pages]}:
        raise ValueError("ordered_ids must contain the dashboard and every page exactly once")
    by_id = {page.id: page for page in pages}
    for order, page_id in enumerate(ordered_ids):
        if page_id == 0:
            get_display_state(session).dashboard_sort_order = order
        else:
            by_id[page_id].sort_order = order
            by_id[page_id].updated_at = utc_now()
    session.flush()
    bump_revision(session)
    return [by_id[page_id] for page_id in ordered_ids if page_id != 0]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_agent(session: Session, name: str, token: str) -> Agent:
    agent = session.scalar(select(Agent).where(Agent.name == name))
    if agent is None:
        agent = Agent(name=name, token_hash=token_hash(token))
        session.add(agent)
    else:
        agent.token_hash = token_hash(token)
        agent.last_seen = utc_now()
    session.flush()
    return agent


def authenticate_agent(session: Session, agent_id: int, token: str) -> Agent | None:
    agent = session.get(Agent, agent_id)
    if agent is None or agent.token_hash != token_hash(token):
        return None
    return agent


def heartbeat_agent(session: Session, agent: Agent) -> Agent:
    agent.last_seen = utc_now()
    session.flush()
    return agent


def create_report(
    session: Session,
    agent: Agent,
    report_type: str,
    payload: dict[str, object],
    ttl_seconds: int | None,
) -> Report:
    now = utc_now()
    report = Report(
        agent_id=agent.id,
        type=report_type,
        payload=payload,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds) if ttl_seconds else None,
    )
    agent.last_seen = now
    session.add(report)
    session.flush()
    bump_revision(session)
    return report


def latest_reports(session: Session) -> list[Report]:
    now = utc_now()
    reports = session.scalars(
        select(Report)
        .where((Report.expires_at.is_(None)) | (Report.expires_at > now))
        .order_by(Report.created_at.desc(), Report.id.desc())
    )
    latest: dict[str, Report] = {}
    for report in reports:
        current = latest.get(report.type)
        if current is None:
            latest[report.type] = report
            continue
        # GitHub is cloud-owned once WebUI collection has produced a report;
        # a legacy HostAgent submission must not replace it merely by arriving later.
        if (
            report.type == "github"
            and current.agent.name != "inkpi-cloud"
            and report.agent.name == "inkpi-cloud"
        ):
            latest[report.type] = report
    return list(latest.values())
