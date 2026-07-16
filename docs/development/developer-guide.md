# Developer Guide

## Layout

| Path | Purpose |
|---|---|
| `backend/src/inkpi/api/` | FastAPI, SQLAlchemy models, SQLite repository, PNG renderer |
| `backend/src/inkpi/display/` | HTTP pull loop and refresh engine |
| `backend/src/inkpi/host_agent/` | Registration, Codex/GitHub collectors, report runner |
| `backend/src/inkpi/network/` | Auth plus network-helper contract and implementation |
| `backend/src/inkpi/hardware/` | Waveshare adapter dependencies and vendor driver |
| `backend/tests/` | Backend unit and service-boundary tests |
| `frontend/` | React Web and fixed 800×480 React eInk view |
| `deploy/` | Current Pi and Ubuntu service templates/installers |

## Setup and Verification

```bash
cd backend
uv sync --extra dev
uv run playwright install chromium
uv run pytest -q
uv run ruff check src/inkpi tests
uv run python -m compileall -q src/inkpi tests
uv build
cd ../frontend
bun install --frozen-lockfile
bun run build
cd ..
git diff --check
```

## Local UI

```bash
mkdir -p tmp
cd backend
uv run inkpi-api \
  --host 127.0.0.1 \
  --port 8080 \
  --database-url sqlite+pysqlite:///../tmp/inkpi.db
```

Open `http://127.0.0.1:8080/`. The Overview page requests the same PNG consumed
by the physical display. For hot reload run `bun run dev` in `frontend/`; Vite proxies
`/api` to port 8080.

Run `bash scripts/smoke_test.sh` to exercise API rendering and display pulling
together in local simulation.

## Rules

- Never import the panel driver outside `backend/src/inkpi/display/`.
- API and React submit complete frames; they do not select refresh modes.
- Add persistent state through SQLAlchemy models, schemas, and repository
  transactions; visual mutations must bump the display revision.
- Keep network commands in the allowlisted helper plan/executor.
- Keep secrets out of SQLite, logs, argv, tests, and documentation.
- Generated previews, databases, caches, and logs belong under ignored `tmp/`
  or tool cache directories and must not be committed.
