# Developer Guide

## Repository layout

| Path | Purpose |
|---|---|
| `backend/src/inkpi/api/` | FastAPI application, SQLite models and repository, PNG renderer |
| `backend/src/inkpi/display/` | HTTP pull loop and refresh engine |
| `backend/src/inkpi/network/` | Authentication and privileged network-helper boundary |
| `backend/src/inkpi/host_agent/` | Host registration, scheduling, and report upload |
| `backend/src/inkpi/services/` | Codex and GitHub domain services |
| `backend/src/inkpi/hardware/` | Waveshare driver and bundled native libraries |
| `backend/tests/` | Backend and service-boundary tests |
| `frontend/src/app/` | Interactive React Web application |
| `frontend/src/eink/` | Fixed-size React eInk view |
| `frontend/src/api/` | Shared HTTP client and response types |
| `deploy/` | systemd templates and installation scripts |
| `scripts/` | Cross-service smoke and hardware checks |

## Prerequisites

- Python 3.12
- `uv`
- Bun
- Chromium installed through Playwright

Pi-only GPIO and SPI dependencies remain in the backend `rpi` optional group.

## Initial setup

```bash
cd backend
uv sync --extra dev
uv run playwright install chromium

cd ../frontend
bun install --frozen-lockfile
bun run build
```

## Run locally

Build the frontend, then start the API from `backend/`:

```bash
mkdir -p ../tmp
uv run inkpi-api \
  --host 127.0.0.1 \
  --port 8080 \
  --database-url sqlite+pysqlite:///../tmp/inkpi.db
```

Open `http://127.0.0.1:8080/`. To exercise the display process in simulation,
run this in another terminal:

```bash
cd backend
uv run inkpi-display --api-url http://127.0.0.1:8080
```

For frontend hot reload, run `bun run dev` in `frontend/`. Vite proxies `/api`
to port 8080. The API must still be running separately.

## Verification

Run backend verification from `backend/`:

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check src/inkpi tests
uv run ruff format --check src/inkpi tests
uv run python -m compileall -q src/inkpi tests
uv build
```

Run frontend and repository verification from the repository root:

```bash
cd frontend && bun run build && cd ..
backend/.venv/bin/mkdocs build --strict
bash scripts/smoke_test.sh
git diff --check
```

The smoke test uses the non-Pi display adapter. Hardware or service changes
also require deployment and physical-panel verification on `meta_pi`.

## Change rules

- Add persistent state through SQLAlchemy models, schemas, and repository
  transactions. Mutations that affect the eInk view must increment the display
  revision in the same transaction.
- Keep physical-panel imports and refresh decisions inside
  `backend/src/inkpi/display/`.
- Submit complete 800×480 frames to the display engine; do not expose refresh
  selection through API or React code.
- Keep privileged network commands in the typed plan/executor under
  `backend/src/inkpi/network/`.
- Keep secrets in protected environment files and out of persisted or logged data.
- Preserve Web/eInk API compatibility when changing shared response types.
- Write generated previews, smoke-test state, databases, and logs under the
  ignored `tmp/` directory.

## Packaging and deployment changes

Run `uv build` after changing Python package paths, console entrypoints, or
package data. After changing service files, run the smoke test and inspect the
rendered templates in `deploy/systemd/`. Deployment procedures are documented
in the [User Manual](../user-manual/deployment.md).
