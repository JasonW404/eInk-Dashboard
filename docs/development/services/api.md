# `inkpi-api`

`inkpi-api` is the process inside the `inkpi-cloud` service. It owns
SQLite state, serves the React build, renders complete eInk PNGs, and exposes
the HTTP contracts consumed by browsers, the display process, and host agents.

## HTTP surface

| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| TODO | `GET/POST /api/todos`, `PATCH/DELETE /api/todos/{id}`, `PUT /api/todos/order` |
| Display | `GET /api/display/revision`, `GET /api/display/image`, `GET /api/display/context`, `POST /api/display/refresh` |
| Settings | `GET /api/settings/system`, `GET /api/settings/network`, `PUT /api/settings/network/hotspot`, `GET /api/settings/integrations`, `PUT /api/settings/integrations/github` |
| Agents | `POST /api/agents/register`, `POST /api/agents/{id}/heartbeat`, `POST /api/agents/{id}/reports` |
| Reports | `GET /api/reports/latest` |
| Pi network | `GET /api/network/commands/next`, `POST /api/network/commands/{id}/result` |
| Frontend | `GET /`, `/todo`, `/settings`, and `/eink.html` when `frontend/dist/` exists |

TODO mutations and reordering increment the display revision transactionally.
Latest-report reads omit expired reports.

GitHub integration tokens are write-only through the HTTP contract and the
SQLite file that contains them is forced to mode `0600`. A normal OpenAI API
key is intentionally not accepted for the Codex card: API organization usage
does not expose the personal ChatGPT/Codex realtime allowance.

## Authentication boundaries

- Hotspot mutation requires `INKPI_ADMIN_TOKEN` and same-origin validation.
- Remote host-agent enrollment requires `INKPI_AGENT_ENROLLMENT_TOKEN`.
- Heartbeat and report upload require the per-agent bearer token returned at
  registration. Only its hash is persisted.
- Revision polling, rendered-image download, and display telemetry use
  `INKPI_DISPLAY_TOKEN`. Without it, those device routes accept loopback only.
- `/api/display/context` is always loopback-only.
- Pi network command polling and results require the separate
  `INKPI_NETWORK_TOKEN`; the Pi needs no inbound listening port.

Health and browser-facing reads remain public to the deployed Web application;
device revision and image routes require the display credential remotely.

## Persistence

The default database is `~/.local/share/inkpi/inkpi.db`. Set
`INKPI_DATABASE_URL` or pass `--database-url` to override it.

The API persists TODOs, display state, hotspot state, agent identities, token
hashes, and expiring reports. It never persists hotspot passwords, GitHub
tokens, admin/display/enrollment tokens, or raw agent bearer tokens.

## PNG renderer

`PlaywrightDisplayRenderer` owns one browser thread and serializes render jobs.
For each uncached revision it creates an isolated 800×480 context, opens the
React eInk page, waits for data and fonts, and captures `.eink-display`. The PNG
is cached by revision and returned with `X-InkPi-Revision` and an ETag.

The renderer generates a complete logical frame. It has no access to SPI/GPIO
and cannot choose a refresh mode.

## Runtime configuration

| Variable | Purpose |
|---|---|
| `INKPI_DATABASE_URL` | SQLite or SQLAlchemy database URL |
| `INKPI_RENDER_BASE_URL` | Loopback URL used by Playwright |
| `INKPI_ADMIN_TOKEN` | Administrative credential |
| `INKPI_DISPLAY_TOKEN` | Remote Pi display credential |
| `INKPI_AGENT_ENROLLMENT_TOKEN` | Remote agent enrollment credential |
| `INKPI_HOTSPOT_PASSWORD` | Optional startup password for local QR rendering |

The cloud systemd unit reads protected values from the root-owned
`/etc/inkpi/cloud.env`.

## Local run

Build `frontend/` first, then run from `backend/`:

```bash
mkdir -p ../tmp
uv run inkpi-api \
  --host 127.0.0.1 \
  --port 8080 \
  --database-url sqlite+pysqlite:///../tmp/inkpi.db
```

OpenAPI is available through FastAPI's default documentation endpoints while
the service is running.
