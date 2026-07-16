# InkPi

InkPi is a Raspberry Pi-centered ambient productivity terminal for a Waveshare
4.26-inch 800×480 four-gray e-ink HAT.

## Runtime

- `inkpi-api`: FastAPI, SQLite application state, React Web, Playwright eInk PNG rendering.
- `inkpi-display`: sole SPI/GPIO owner; pulls revisions and PNGs from the API and applies the existing longevity-first refresh engine.
- `inkpi-network-helper`: narrowly scoped root helper for allowlisted NetworkManager changes.
- `inkpi-host-agent`: optional Ubuntu collector for Codex usage and GitHub contributions.

There is one state path (SQLite), one browser UI (React), and one physical-panel
owner (`inkpi-display`). The removed Python dashboard/core/admin runtime is not
part of v1.

## Repository

- `frontend/`: Bun, Vite, React Web, and the fixed 800×480 eInk view.
- `backend/`: Python package, service entrypoints, and backend tests.
- `deploy/`: systemd templates and installation scripts.
- `scripts/`: repository-wide smoke and hardware verification scripts.
- `docs/`: architecture, service, development, and deployment documentation.

## Development

```bash
cd backend
uv sync --extra dev
uv run playwright install chromium
uv run pytest -q
uv run ruff check src/inkpi tests
cd ../frontend
bun install --frozen-lockfile
bun run build
cd ..
bash scripts/smoke_test.sh
```

Run locally:

```bash
mkdir -p tmp
cd backend
uv run inkpi-api --database-url sqlite+pysqlite:///../tmp/inkpi.db
```

Open `http://127.0.0.1:8080/`. The Overview page includes the current 800×480
eInk preview. Run the simulated display puller separately when testing the full
two-service path:

```bash
cd backend
uv run inkpi-display --api-url http://127.0.0.1:8080
```

## Raspberry Pi

```bash
cd backend
uv sync --extra rpi
uv run playwright install chromium
cd ../frontend
bun install --frozen-lockfile
bun run build
cd ..
sudo bash deploy/install_pi.sh
```

See the [User Manual](docs/user-manual/index.md),
[Architecture](docs/development/architecture.md), and
[Developer Guide](docs/development/developer-guide.md).
