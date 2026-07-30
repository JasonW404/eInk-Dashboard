# `inkpi-host-agent`

`inkpi-host-agent` is an optional Ubuntu-side collector. It does not own
application state, serve Web pages, or control the eInk panel. It registers
with the Pi API, sends heartbeats, and uploads expiring Codex and GitHub reports.

Codex quota collection remains HostAgent-owned because it requires the
authenticated local Codex CLI session. When GitHub collection is enabled in
the Cloud WebUI, Cloud owns the GitHub report and takes precedence over legacy
GitHub reports submitted by a HostAgent.

## Collectors

| Collector | Source | Default interval |
|---|---|---:|
| `codex` | Local Codex CLI app-server API | 300 seconds |
| `github` | GitHub GraphQL with REST fallback | 21,600 seconds |

Codex collection reports the plan, usage windows, remaining percentage, and
reset times. `CODEX_BINARY` can override binary discovery.

GitHub collection is scoped to the configured username rather than repository
ownership. The primary GraphQL path reports current-month commits, pull
requests, and daily contribution counts across visible personal,
organization, collaborator, and private repositories. Private data requires a
token with the necessary repository and organization authorization. The REST
fallback uses configured user, organization, and extra repositories.

A collector failure is logged without stopping heartbeat or the other
collector. Report TTL is three times its collector interval, with a minimum of
60 seconds.

## Configuration

Non-secret collector configuration lives in
`~/.config/inkpi/config.json`:

```json
{
  "schema_version": 1,
  "github": {
    "username": "your-user",
    "organization": "your-org",
    "commit_email": "",
    "extra_repos": []
  },
  "scheduler": {
    "github_interval_seconds": 21600,
    "codex_interval_seconds": 300,
    "codex_rpc_timeout_seconds": 20
  }
}
```

Supply the GitHub token through `EINK_GITHUB_API_KEY` or
`EINK_GITHUB_TOKEN`, not through JSON.

## Enrollment

Set the same one-time `INKPI_AGENT_ENROLLMENT_TOKEN` on the Pi API and the host.
Registration returns an agent token once. The host stores it in
`~/.config/inkpi/host-agent.json` with mode `0600`; the Pi stores only its hash.

Run a single collection cycle from `backend/`:

```bash
export INKPI_API_URL='http://inkpi.local:8080'
export INKPI_AGENT_NAME='ubuntu-main'
export INKPI_AGENT_ENROLLMENT_TOKEN='replace-with-a-long-random-value'
uv run inkpi-host-agent --once
```

After successful registration, remove the enrollment token from the host
environment unless re-enrollment is required.

## Binary installation

The standalone HostAgent is bundled with each cloud release. Enable it through
the extracted cloud installer:

```bash
sudo ./install.sh \
  --enable-host-agent \
  --host-agent-api-url http://127.0.0.1:8080 \
  --host-agent-name homelab-cloud
```

The installer reads the enrollment token from the root-owned cloud environment,
creates the HostAgent environment, waits for credentials, removes the one-time
token, and restarts the service. The deployed host does not need Python or
`uv`.
