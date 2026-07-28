# InkPi Engineering Guidelines

InkPi has a cloud control plane for FastAPI/SQLite/React/Playwright and a
lightweight Raspberry Pi display client that polls complete frames.

## Boundaries

- Only `backend/src/inkpi/display/` may import the Waveshare driver or select refresh actions.
- API and React produce complete 800×480 logical frames only.
- Only `inkpi-cloud` persists application state and renders logical frames.
- The Pi runtime contains no API, database, browser, frontend toolchain, or integrations.
- Do not restore the removed `inkpi-core`, `inkpi-admin`, Python dashboard/UI renderer, or Unix-socket frame push path.
- Keep secrets in protected environment files and out of persistence, logs, argv, tests, and docs.

## Workflow

Use Python 3.12 with `uv` in `backend/` and Bun in `frontend/`. Run tests, Ruff, compileall,
`bun run build`, `git diff --check`, and the two-service smoke test before handoff.
