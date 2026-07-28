# InkPi Documentation

InkPi is a cloud-rendered ambient productivity terminal with a lightweight
Raspberry Pi client and an 800×480 e-ink panel.

## Components

| Component | Responsibility |
|---|---|
| `inkpi-cloud` | SQLite state, HTTP API, React Web, integrations, and eInk PNG rendering |
| `inkpi-display` | Authenticated PNG polling, panel ownership, and refresh policy |
| `inkpi-host-agent` | Optional Codex and GitHub report collection to the cloud |

Documentation is organized into two sections:

- The [User Manual](user-manual/index.md) covers installation, deployment, and
  day-to-day access to InkPi.
- The [Development Docs](development/index.md) cover architecture, services,
  frontend and eInk behavior, local development, and testing.
