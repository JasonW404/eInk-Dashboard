# inkpi-api Service

`inkpi-api` is the v1.0 application-state boundary introduced by
[`update.md`](../update.md). It runs on the Raspberry Pi and owns the SQLite
database used by both InkPi Web and the dedicated eInk renderer.

## API surface

The current implementation provides:

- `GET /api/health`
- `GET /api/todos`
- `POST /api/todos`
- `PATCH /api/todos/{id}`
- `DELETE /api/todos/{id}`
- `PUT /api/todos/order`
- `GET /api/display/revision`
- `GET /api/display/context` (local render-only hotspot facts)
- `GET /api/display/image` (Playwright-rendered `800x480` PNG)
- `POST /api/display/refresh` (display-owned refresh telemetry)
- `GET /api/settings/system`
- `GET /api/settings/network`
- `PUT /api/settings/network/hotspot`
- agent registration, heartbeat, report upload, and latest-report reads
- the built React application at `/`, `/todo`, and `/settings` when `frontend/dist`
  exists
- the fixed React eInk render view at `/eink.html`

Every TODO mutation and reorder increments the persistent display revision in
the same database transaction. The API never controls GPIO, submits frames, or
chooses a refresh mode.

## Local development

Build the Web application with Bun:

```bash
cd frontend
bun install --frozen-lockfile
bun run build
cd ../backend
uv run playwright install chromium
```

Run the API with an isolated local database:

```bash
mkdir -p ../tmp
uv run inkpi-api \
  --host 127.0.0.1 \
  --port 8080 \
  --database-url sqlite+pysqlite:///../tmp/inkpi.db
```

The default persistent database is
`~/.local/share/inkpi/inkpi.db`. Override it with `INKPI_DATABASE_URL` or the
`--database-url` option.

For frontend hot reload, run `bun run dev` in `frontend/`; Vite proxies `/api` to
`127.0.0.1:8080`.

The API keeps a headless Chromium process behind a dedicated renderer thread,
creates an isolated `800x480` page per revision, waits for React data and fonts,
then screenshots only `.eink-display`. PNG bytes are cached by revision.

## Network and secret boundary

Settings enables, disables, and replaces the Wi-Fi hotspot through the existing
allowlisted privileged helper. `inkpi-api` remains unprivileged. Passwords are
accepted for the current mutation, sent over the permission-restricted helper
socket, passed to `nmcli --ask` through stdin, and omitted from SQLite,
operation history, API responses, command arguments, and logs. Mutations
require `INKPI_ADMIN_TOKEN` and reject cross-origin requests.

Only enable state, SSID, and update time persist. Connected-client count is a
read-only fact from reachable `wlan0` ARP neighbors. The normal settings API
never returns a password. When a hotspot is active, the local-only display
context may expose an ephemeral standard Wi-Fi QR payload to the local Chromium
renderer. Its password comes from the current mutation or
`INKPI_HOTSPOT_PASSWORD`; it is never written to SQLite. Remote clients cannot
read this render-only endpoint, while the resulting QR remains visible in the
rendered eInk image by design.

Display telemetry records the last accepted refresh time. It never selects or
changes refresh mode; that remains an `inkpi-display` decision.

`inkpi-display` polls revision, debounces changes, downloads the PNG, and
submits the complete frame to the longevity-first `DisplayEngine`. API and
React code cannot select refresh modes.
