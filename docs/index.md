# InkPi Documentation

InkPi is a local-first ambient productivity terminal built around a Raspberry
Pi and an 800×480 e-ink panel.

## Components

| Component | Responsibility |
|---|---|
| `inkpi-api` | SQLite state, HTTP API, React Web, eInk PNG rendering |
| `inkpi-display` | Panel ownership and refresh policy |
| `inkpi-network-helper` | Allowlisted privileged network mutations |
| `inkpi-host-agent` | Optional Codex and GitHub report collection |

Documentation is organized into two sections:

- The [User Manual](user-manual/index.md) covers installation, deployment, and
  day-to-day access to InkPi.
- The [Development Docs](development/index.md) cover architecture, services,
  frontend and eInk behavior, local development, and testing.
