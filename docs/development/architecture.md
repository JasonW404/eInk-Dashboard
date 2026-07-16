# Architecture

This page describes the runtime implemented in the current repository.

## Runtime topology

```text
Browser ──HTTP──> inkpi-api ───────────────> SQLite
                     │
                     ├── React eInk page ──Playwright──> 800×480 PNG
                     ├── protected Unix socket ──> inkpi-network-helper ──> NetworkManager
                     └── revision + PNG <──poll── inkpi-display ──> Waveshare HAT

Ubuntu inkpi-host-agent ──authenticated, expiring reports──> inkpi-api
```

| Process | Runs on | Responsibility |
|---|---|---|
| `inkpi-api` | Raspberry Pi | HTTP API, SQLite state, Web assets, and logical PNG generation |
| `inkpi-display` | Raspberry Pi | SPI/GPIO ownership and all physical refresh decisions |
| `inkpi-network-helper` | Raspberry Pi as root | Allowlisted NetworkManager mutations |
| `inkpi-host-agent` | Optional Ubuntu host | Codex and GitHub collection |

The React application has two entry points: the interactive Web UI and a fixed
800×480 eInk view. They consume the same API but serve different presentation
requirements.

## Ownership boundaries

- `inkpi-api` is the only application-state owner. It persists TODOs, agents,
  reports, display revision and telemetry, and non-secret hotspot settings.
- `inkpi-display` is the only SPI/GPIO owner. The API supplies complete logical
  frames and cannot request full or partial refreshes.
- `inkpi-network-helper` is the only root process. It accepts typed,
  allowlisted operations over a permission-restricted local socket.
- `inkpi-host-agent` supplies authenticated, expiring data. The Pi remains the
  source of truth when the host is offline.
- Secrets are supplied through protected environment files. They do not belong
  in SQLite, JSON configuration, logs, tests, documentation, or command
  arguments.

## Application and display flow

1. A visual state mutation commits to SQLite and increments `display_state.revision`.
2. `inkpi-display` polls `/api/display/revision` and debounces a new revision.
3. `/api/display/image` asks Playwright to open `/eink.html` at an 800×480 viewport.
4. React fetches the current TODO, report, revision, and local display context data.
5. Playwright waits for the ready marker and bundled fonts, then screenshots
   only `.eink-display`.
6. `DisplayEngine` compares the complete frame with its previous accepted frame
   and chooses full, partial, region repair, or skip.
7. The display process reports accepted refresh telemetry back to the API.

PNG output is cached by display revision. Slow browser rendering and physical
panel refreshes run outside API request-control paths that do not require them.

## Data model

| Table | Stored state |
|---|---|
| `todos` | Title, completion, eInk visibility, order, timestamps |
| `display_state` | Revision, refresh timestamps, accepted refresh count |
| `hotspot_settings` | Enabled state, SSID, update time; never the password |
| `agents` | Agent identity, token hash, heartbeat timestamps |
| `reports` | Typed JSON payload, source agent, creation and expiry times |

The SQLite database defaults to `~/.local/share/inkpi/inkpi.db` and is owned by
`inkpi-api`.

## Network and secret flow

Hotspot mutations require the API admin token and same-origin validation. The
unprivileged API sends a typed request to the network helper, which invokes
`nmcli --ask` and supplies the password through stdin. Only enabled state and
SSID are persisted.

When the hotspot is active, the password may be held briefly in API memory to
produce the Wi-Fi QR payload for the loopback-only display context endpoint.
The normal settings API never returns it.

Host-agent enrollment uses a one-time enrollment token. The API returns an
agent bearer token once and stores only its SHA-256 hash. Uploaded reports have
an expiry time and disappear from latest-report reads when stale.

## Failure behavior

- If the host agent is offline, its reports become stale; local Web, TODO, and
  display functions continue.
- If rendering fails, `/api/display/image` returns `503` and the display keeps
  its last accepted frame.
- If a panel refresh fails, the engine clears previous-frame state so the next
  accepted frame uses full recovery.
- If the network helper is unavailable, hotspot mutation fails without
  changing persisted hotspot state.
