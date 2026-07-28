# Architecture

## Runtime topology

```text
Cloud server
  Browser ──HTTPS──> inkpi-cloud ──> SQLite
                         │
                         ├── integrations and report processing
                         └── React eInk view ──Playwright──> cached 800×480 PNG
                                      ▲
                                      │ authenticated revision/PNG polling
                                      │
Raspberry Pi                    inkpi-display ──SPI/GPIO──> Waveshare HAT
```

| Process | Runs on | Responsibility |
|---|---|---|
| `inkpi-cloud` | Cloud Linux host or LXC | HTTP API, SQLite, Web UI, integrations, uploads, scheduling, and PNG rendering |
| `inkpi-display` | Raspberry Pi | Authenticated frame polling and physical refresh policy |
| `inkpi-host-agent` | Optional data source | Collection and authenticated report upload |

## Ownership boundaries

- The cloud service owns all application state and expensive work. It emits a
  complete display-ready 800×480 PNG.
- The Pi has no database and does not render HTML. It validates the PNG, converts
  it to the panel grayscale format, compares it with the last accepted frame,
  and decides whether to use a full, partial, repaired, or skipped refresh.
- Only `inkpi-display` accesses SPI/GPIO.
- A shared display bearer token authenticates revision reads, image downloads,
  and refresh telemetry. Cloud access should additionally be protected by TLS.
- If the cloud or network is unavailable, the Pi retains the last accepted
  image and retries without clearing the panel.

## Frame flow

1. A cloud-side visual state mutation increments the display revision.
2. The Pi polls `GET /api/display/revision` with its bearer token.
3. After debouncing a new revision, it requests `GET /api/display/image`.
4. The cloud selects the scheduled page and either serves its prepared image or
   uses Playwright to render the fixed React eInk view.
5. The Pi accepts only PNG frames of exactly 800×480 pixels.
6. The local display engine chooses the physical refresh method.
7. The Pi sends the result to `POST /api/display/refresh`.

The image response carries `X-InkPi-Revision`. The Pi records that revision only
after the engine accepts the frame, preventing failed refreshes from being
treated as current.

## Dependencies

The Python package exposes distinct extras:

- Base: `requests` and Pillow, shared with the Pi display client.
- `rpi`: GPIO and SPI drivers only.
- `cloud`: FastAPI, SQLAlchemy, Uvicorn, and Playwright.
- `dev`: cloud dependencies plus test and lint tooling.

Chromium, Bun, frontend sources, SQLite, and cloud integrations are not required
by the Pi runtime.

Tagged releases freeze these environments into PyInstaller one-directory
bundles. Cloud bundles add the prebuilt React output; display bundles contain
only the display process and panel dependencies. Native amd64 and arm64 bundles
are built independently to avoid cross-architecture Python extension issues.
