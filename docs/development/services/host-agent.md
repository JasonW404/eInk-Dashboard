# inkpi-host-agent Service

`inkpi-host-agent` is the optional Ubuntu-side data provider described in the
v1.0 architecture. It does not host Web pages, control the eInk panel, or own
application state. It only collects external data and uploads expiring reports
to the Raspberry Pi API.

## Collectors

The initial process contains two independent collectors:

- `CodexCollector`: Codex plan and usage windows via the local Codex CLI.
- `GitHubCollector`: username-scoped monthly commits, pull requests, and daily
  contribution calendar through GitHub GraphQL `contributionsCollection`.

The GitHub collector uses the configured Username rather than repository
ownership, so qualifying contributions can come from personal, organization,
collaborator, and other repositories. Private totals require a token that can
read the relevant repositories, any required organization SSO authorization,
and the GitHub profile setting that exposes private contribution counts. When
GraphQL contribution collection is unavailable, the legacy per-repository REST
collector remains as a compatibility fallback.

Each collector has its own interval. A collector failure is logged without
stopping heartbeat or the other collector.

## Registration and secrets

Set the same one-time enrollment secret on the Pi API and Ubuntu host. The Pi
returns an agent token once; the host stores it in
`~/.config/inkpi/host-agent.json` with mode `0600`. The Pi database stores only
its SHA-256 hash.

No token is written to editable InkPi JSON configuration or logs.

## Run once

On the Raspberry Pi:

```bash
cd backend
export INKPI_AGENT_ENROLLMENT_TOKEN='replace-with-a-long-random-value'
uv run inkpi-api --host 0.0.0.0 --port 8080
```

On Ubuntu:

```bash
cd backend
export INKPI_API_URL='http://inkpi.local:8080'
export INKPI_AGENT_NAME='ubuntu-main'
export INKPI_AGENT_ENROLLMENT_TOKEN='replace-with-a-long-random-value'
uv run inkpi-host-agent --once
```

Subsequent runs reuse the saved agent token. The enrollment token can then be
removed from the host environment unless registration must be repeated.

## systemd on Ubuntu

Create the protected environment file:

```bash
mkdir -p ~/.config/inkpi
cat > ~/.config/inkpi/host-agent.env <<'EOF'
INKPI_API_URL=http://inkpi.local:8080
INKPI_AGENT_NAME=ubuntu-main
INKPI_AGENT_ENROLLMENT_TOKEN=replace-with-a-long-random-value
EOF
chmod 600 ~/.config/inkpi/host-agent.env
cd /path/to/InkPi
sudo bash deploy/install_host_agent.sh
```

After the first successful registration, remove
`INKPI_AGENT_ENROLLMENT_TOKEN` from this file and restart the service.

```bash
systemctl status inkpi-host-agent.service
journalctl -u inkpi-host-agent.service -f
```
