# InkPi Agent And Codebase Declaration

All contributors and coding agents must follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Current Runtime

- Target: Raspberry Pi 4B and Waveshare 4.26-inch 800×480 four-gray e-ink HAT.
- Pi services: `inkpi-api`, `inkpi-display`, `inkpi-network-helper`.
- Optional Ubuntu service: `inkpi-host-agent`.
- State: SQLite owned by `inkpi-api`; secrets come from protected environment files.
- UI: React Web plus a dedicated fixed-size React eInk view.
- Rendering: local Playwright generates exact 800×480 PNG frames.

## Non-Negotiable Boundaries

1. `inkpi-display` is the sole SPI/GPIO and physical-panel owner.
2. Full, partial, skipped, and recovery decisions stay in `backend/src/inkpi/display/`.
3. `inkpi-api` owns application state and complete logical frame generation; it never selects a refresh mode.
4. `inkpi-network-helper` is the only root process and accepts allowlisted typed operations only.
5. Host-agent reports are authenticated, expiring inputs; the Pi remains the source of truth.
6. Secrets must not enter SQLite, editable JSON, logs, tests, documentation, or command arguments.

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
