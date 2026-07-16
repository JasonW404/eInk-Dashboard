# InkPi Engineering Guidelines

InkPi v1 has one runtime architecture: FastAPI/SQLite/React on the Pi, a
revision-aware display puller, a privileged allowlisted network helper, and an
optional Ubuntu host agent.

## Boundaries

- Only `backend/src/inkpi/display/` may import the Waveshare driver or select refresh actions.
- API and React produce complete 800×480 logical frames only.
- Only `inkpi-api` persists application state.
- Only `inkpi-network-helper` executes privileged NetworkManager operations.
- Do not restore the removed `inkpi-core`, `inkpi-admin`, Python dashboard/UI renderer, or Unix-socket frame push path.
- Keep secrets in protected environment files and out of persistence, logs, argv, tests, and docs.

## Workflow

Use Python 3.12 with `uv` in `backend/` and Bun in `frontend/`. Run tests, Ruff, compileall,
`bun run build`, `git diff --check`, and the two-service smoke test before handoff.
