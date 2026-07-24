# InkPi Agent And Codebase Declaration

All contributors and coding agents working in this repository must follow
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Current Status

- Project name: **InkPi**
- Version: `0.2.1`
- Target: Raspberry Pi 4B with Waveshare 4.26-inch `800x480` e-ink HAT
- Architecture: hybrid multi-process runtime
- Main services: `inkpi-core`, `inkpi-display`, and `inkpi-admin`
- Built-in pages: `overview` (registered); `codex_usage` panel exists but is
  not yet a standalone page
- Configuration: versioned JSON owned by core, secrets supplied through `.env`
- Management state: read-only system/network facts and dashboard controls exist;
  admin portal serves LAN/hotspot access; NetworkManager write controls are
  future work
- Font state: all rendering fonts are bundled in `inkpi/fonts/` with no system
  font fallbacks; architecture tests enforce this policy
- CI state: GitHub Actions runs test (macOS+Ubuntu), ruff lint, and dual-service
  smoke test on every push and PR
- Deployment target: `meta_pi:/home/meta/Workspace/InkPi`

## Non-Negotiable Boundaries

1. `inkpi-display` is the sole SPI/GPIO and physical-panel owner.
2. Full, partial, skipped, and recovery refresh decisions happen only inside
   `inkpi/display/`.
3. Dashboard pages submit complete logical frames and cannot request refresh
   modes or import display implementations.
4. `inkpi-core` owns scheduling, service orchestration, and atomic configuration
   persistence.
5. Management owns system/network facts. Dashboard and management share data or
   controls only through typed contracts.
6. Cross-process APIs use versioned contracts over local Unix sockets.
7. Slow collection, rendering, or display refresh must not block control/status
   requests.
8. At least one dashboard page must remain enabled.
9. Secrets must not enter editable JSON configuration, logs, tests, or docs.

## Engineering Rules

- Use Python 3.12 and `uv`; never use `pip`, `python -m venv`, or `virtualenv`.
- Keep Pi-only dependencies in the `rpi` optional dependency group.
- Preserve existing user changes and staged work.
- Extend current contracts and modules before inventing parallel abstractions.
- Keep new display-driver dependencies and policy out of dashboard/management.
- Keep privileged network operations out of core and the future portal; use a
  narrowly scoped helper.
- Update architecture and developer documentation when boundaries or operations
  change.

## Required Verification

For normal changes:

```bash
uv sync --extra dev
uv run pytest -q
uv run python -m compileall -q inkpi tests
git diff --check
```

For packaging or entrypoint changes, also run `uv build`.

For page changes, render and inspect the relevant `inkpi-preview` output.
Preview images created for tests or local simulation must be written under the
project `tmp/` directory, not system `/tmp`.

For display, service, or deployment changes, run a local two-service smoke test
and then validate on `meta_pi`. Clearly report whether verification was
simulation-only or used the physical panel.

## Deployment and Real-World Testing

- Use `ssh meta_pi` to access the target device.
- Deploy with local `.env` file.

## Key References

- [Documentation Home](docs/index.md) (MkDocs site: `uv run mkdocs serve`)
- [About InkPi](docs/about.md)
- [Architecture](docs/architecture.md)
- [Developer Guide](docs/guides/developer-guide.md)
- [Deployment Guide](docs/guides/deployment.md)
- [Development Plan](docs/development/plan.md)
- [Example Configuration](config/inkpi.example.json)
- [Engineering Guidelines](.github/copilot-instructions.md)
