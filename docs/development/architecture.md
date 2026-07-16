# Architecture

```text
Browser ──HTTP──> inkpi-api ──> SQLite
                     │
                     ├── React eInk view ──Playwright──> 800×480 PNG
                     ├── protected helper socket ──> inkpi-network-helper ──> NetworkManager
                     └── revision + PNG <──poll── inkpi-display ──> Waveshare HAT

Ubuntu inkpi-host-agent ──authenticated expiring reports──> inkpi-api
```

## Ownership

- `inkpi-api` is the single application-state owner. TODOs, reports, display
  revision, refresh telemetry, and non-secret hotspot state live in SQLite.
- React Web and React eInk are separate views over the same HTTP data.
- Playwright screenshots only the fixed `.eink-display` element.
- `inkpi-display` owns SPI/GPIO, previous-frame state, queuing, dirty-region
  analysis, and every refresh decision.
- The root network helper accepts only typed, allowlisted operations. Passwords
  cross its protected socket and stdin but are never persisted or placed in argv.
- The host agent is optional. Its loss makes Codex/GitHub data stale without
  affecting local state, Web, or display ownership.

## Display Flow

1. A state mutation increments the persistent display revision.
2. `inkpi-display` polls the revision and debounces changes.
3. It downloads a complete 800×480 PNG from `/api/display/image`.
4. `DisplayEngine` compares the frame with its predecessor.
5. The engine chooses full, partial, region repair, or skip and reports telemetry.

The API cannot request a refresh mode. Startup, recovery, page changes,
grayscale transitions, large changes, and partial-streak limits force a full
refresh. Small monochrome changes may use region-aligned partial refreshes.

## Secrets

GitHub tokens, admin/display/agent tokens, and the hotspot password are supplied
through protected environment files. The hotspot password may exist briefly in
API memory to produce a local-only Wi-Fi QR payload; it does not enter SQLite.
