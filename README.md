# InkPi

InkPi is a cloud-rendered ambient productivity dashboard for a Waveshare
4.26-inch 800×480 four-gray e-ink HAT.

## Runtime

InkPi has two independent deployment roles:

- `inkpi-cloud`: FastAPI, SQLite state, integrations, React Web, and Playwright
  generation of complete 800×480 PNG frames.
- `inkpi-display`: a lightweight Raspberry Pi client that authenticates to the
  cloud API, polls revisions, downloads PNGs, and owns all SPI/GPIO refresh
  decisions.
- `inkpi-host-agent`: an optional collector that sends Codex and GitHub reports
  to the cloud API.

The Pi does not run the Web UI, API, database, frontend toolchain, Chromium, or
application integrations.

## Repository

- `frontend/`: Bun, Vite, React Web, and the fixed 800×480 cloud render view.
- `backend/`: shared Python package, cloud API, Pi display client, and tests.
- `packaging/`: standalone binary definitions and release-bundle installers.
- `deploy/`: environment examples, systemd units, and uninstallers.
- `scripts/`: smoke and hardware verification.
- `docs/`: architecture, development, and deployment documentation.

## Binary releases

Each tagged release publishes four native Linux bundles:

- `inkpi-cloud-<version>-linux-amd64.tar.gz`
- `inkpi-cloud-<version>-linux-arm64.tar.gz`
- `inkpi-display-<version>-linux-amd64.tar.gz`
- `inkpi-display-<version>-linux-arm64.tar.gz`

The archives contain standalone executables, deployment scripts, systemd
templates, and configuration examples. Deployment does not require Python,
`uv`, Bun, Node.js, or source compilation. See the
[deployment guide](docs/user-manual/deployment.md).

Installers run as root and always create/use the non-login `inkpi` system
account. The cloud archive also contains the optional HostAgent, enabled with
`./install.sh --enable-host-agent`. First installation interactively collects
required API tokens into root-owned configuration; `--reconfigure` replaces
saved values.

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
```

Run the cloud control plane:

```bash
mkdir -p tmp
cd backend
uv run inkpi-api --database-url sqlite+pysqlite:///../tmp/inkpi.db
```

Run a simulated Pi client separately:

```bash
cd backend
INKPI_DISPLAY_TOKEN=development-token \
  uv run inkpi-display --api-url http://127.0.0.1:8080
```

See the [deployment guide](docs/user-manual/deployment.md) and
[architecture](docs/development/architecture.md).
