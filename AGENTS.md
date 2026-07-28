# InkPi Agent And Codebase Declaration

All contributors and coding agents must follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Current Runtime

- Cloud service: `inkpi-cloud` owns FastAPI, SQLite, integrations, React Web,
  scheduling, uploads, and Playwright rendering.
- Pi service: `inkpi-display` only polls authenticated revisions/PNGs and owns
  the Waveshare 4.26-inch 800×480 panel.
- Optional service: `inkpi-host-agent` reports to the cloud API.
- The Pi runtime must not depend on Bun, Chromium, FastAPI, SQLAlchemy, or a
  local application database.
- Tagged deployment artifacts are native PyInstaller bundles for Linux amd64
  and arm64; deployment targets must not require Python, uv, or Bun.

## Non-Negotiable Boundaries

1. `inkpi-display` is the sole SPI/GPIO and physical-panel owner.
2. Full, partial, skipped, and recovery decisions stay in `backend/src/inkpi/display/`.
3. `inkpi-cloud` owns application state and complete logical frame generation;
   it never selects a physical refresh mode.
4. The display bearer token protects all remote device endpoints and must not
   enter logs, tests, documentation values, or command arguments.
5. Host-agent reports are authenticated, expiring cloud inputs.

## Engineering Rules

- Use Python 3.12 and `uv` in `backend/`; use Bun in `frontend/`.
- Keep Pi-only dependencies in the `rpi` optional group.
- Preserve unrelated user changes.
- Extend the HTTP/SQLite contracts instead of reintroducing core/admin Unix-socket orchestration.
- Write local previews and smoke-test state under `tmp/`.

## Required Verification

```bash
cd backend
uv sync --extra dev
uv run pytest -q
uv run ruff check src/inkpi tests
uv run python -m compileall -q src/inkpi tests
cd ../frontend && bun run build && cd ..
git diff --check
```

For entrypoint changes also run `uv build`. For service changes run
`bash scripts/smoke_test.sh`. Hardware changes require verification on
`meta_pi:/home/meta/Workspace/InkPi` and a clear simulation-vs-panel report.
