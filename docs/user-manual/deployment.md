# Deployment Guide

Target: `meta_pi:/home/meta/Workspace/InkPi` on Raspberry Pi OS with the
Waveshare 4.26-inch 800×480 HAT.

## Synchronize and Build

```bash
rsync -avz --delete \
  --exclude='.git' --exclude='.venv' --exclude='node_modules' \
  --exclude='tmp' --exclude='site' --exclude='dist' \
  ./ meta_pi:/home/meta/Workspace/InkPi/

ssh meta_pi
cd ~/Workspace/InkPi
cd backend
uv sync --extra rpi
uv run playwright install chromium
cd ../frontend
bun install --frozen-lockfile
bun run build
cd ..
```

## Protected Environment Files

Create `~/.config/inkpi/api.env` with mode `0600` as needed:

```text
INKPI_ADMIN_TOKEN=replace-with-a-local-token
INKPI_DISPLAY_TOKEN=replace-with-a-display-token
INKPI_AGENT_ENROLLMENT_TOKEN=replace-with-an-enrollment-token
INKPI_HOTSPOT_PASSWORD=current-hotspot-password
```

GitHub credentials for the optional host agent belong in its protected service
environment as `EINK_GITHUB_API_KEY`. Non-secret display/GitHub collection
settings may live in `~/.config/inkpi/config.json`.

## Install Pi Services

```bash
sudo bash deploy/install_pi.sh
systemctl status inkpi-network-helper.service inkpi-api.service inkpi-display.service
```

The installer disables conflicts from pre-v1 service names before
enabling the current helper, API, and display units.

## Verify

```bash
curl http://127.0.0.1:8080/api/health
curl http://127.0.0.1:8080/api/display/revision
journalctl -u inkpi-api.service -u inkpi-display.service \
  -u inkpi-network-helper.service --since '10 minutes ago'
```

Confirm the Web UI is reachable at `http://<pi-ip>:8080/`, then compare its
eInk preview with the physical panel. Report explicitly whether verification
was simulation-only or used the HAT.

Install the optional Ubuntu collector with:

```bash
sudo bash deploy/install_host_agent.sh
```
