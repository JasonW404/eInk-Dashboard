"""Transactional operations over InkPi's single persistent state store."""

from __future__ import annotations

from datetime import timedelta
import hashlib
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from inkpi.api.models import Agent, DisplayPage, DisplayState, HotspotSettings, Report, Todo, utc_now
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
        hotspot_columns = {
            row[1] for row in session.connection().exec_driver_sql("PRAGMA table_info(hotspot_settings)")
        }
        if hotspot_columns and "security" not in hotspot_columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE hotspot_settings ADD COLUMN security VARCHAR(16) NOT NULL DEFAULT 'wpa2'"
            )
        if session.get(DisplayState, 1) is None:
            session.add(DisplayState(id=1))
        else:
            state = get_display_state(session)
            if not isinstance(state.revision, str) or len(state.revision) != 36:
                state.revision = str(uuid4())
        if session.get(HotspotSettings, 1) is None:
            session.add(HotspotSettings(id=1))


def list_todos(session: Session) -> list[Todo]:
    return list(session.scalars(select(Todo).order_by(Todo.sort_order, Todo.id)))


def get_todo(session: Session, todo_id: int) -> Todo | None:
    return session.get(Todo, todo_id)


def create_todo(session: Session, payload: TodoCreate) -> Todo:
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
    removed_order = todo.sort_order
    session.delete(todo)
    session.flush()
    session.execute(update(Todo).where(Todo.sort_order > removed_order).values(sort_order=Todo.sort_order - 1))
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
) -> HotspotSettings:
    settings = get_hotspot_settings(session)
    settings.enabled = enabled
    settings.ssid = ssid
    settings.security = security
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
        raise ValueError("ordered_ids must contain the dashboard and every photo page exactly once")
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
        latest.setdefault(report.type, report)
    return list(latest.values())
