# Deployment Guide

InkPi uses separate installers for the Raspberry Pi appliance and the optional
Ubuntu host agent. Both installers prepare the Python environment, render and
validate systemd units, preserve replaced units as timestamped backups, enable
the services, and perform post-install checks.

## Raspberry Pi

### Requirements

- Raspberry Pi 4B with a 64-bit ARM Linux installation
- Waveshare 4.26-inch 800×480 HAT
- Python 3.12
- `uv` installed for the non-root service user
- Bun installed for the same user
- NetworkManager available for hotspot control
- Repository checked out on the Pi

The installer rejects a 32-bit OS because the Playwright browser deployment is
prepared for Linux ARM64.

### Copy the repository

The configured target is `meta_pi:/home/meta/Workspace/InkPi`:

```bash
rsync -avz --delete \
  --exclude='.git' --exclude='.venv' --exclude='node_modules' \
  --exclude='tmp' --exclude='site' --exclude='dist' \
  ./ meta_pi:/home/meta/Workspace/InkPi/
```

### Configure secrets

On the Pi, create the protected API environment file as the service user:

```bash
cd ~/Workspace/InkPi
install -d -m 700 ~/.config/inkpi
install -m 600 deploy/env/api.env.example ~/.config/inkpi/api.env
${EDITOR:-nano} ~/.config/inkpi/api.env
```

`INKPI_ADMIN_TOKEN` is required. `INKPI_AGENT_ENROLLMENT_TOKEN` must match the
Ubuntu host during its first registration. Keep `INKPI_DISPLAY_TOKEN` when the
display telemetry should be explicitly authenticated. The hotspot password is
optional until hotspot QR rendering is needed.

Generate independent tokens rather than reusing one value:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Install or update

```bash
sudo bash deploy/install_pi.sh
```

The installer:

1. verifies Linux ARM64 and an unprivileged service user;
2. validates ownership and permissions of `api.env`;
3. runs `uv sync --extra rpi`;
4. installs Chromium system dependencies and the user-owned browser binary;
5. installs frontend dependencies and builds `frontend/dist/` with Bun;
6. adds the service user to existing `spi` and `gpio` groups;
7. renders and validates the three systemd units;
8. disables conflicting legacy services;
9. starts the helper, API, and display in order;
10. verifies service state and `/api/health`.

When the script is invoked directly as root rather than through `sudo`, select
the service account explicitly:

```bash
sudo INKPI_SERVICE_USER=meta bash deploy/install_pi.sh
```

Rerun the same installer after updating the checkout. Existing unit files are
copied to timestamped `.bak.*` files before replacement.

### Verify the device

```bash
systemctl status inkpi-network-helper.service inkpi-api.service inkpi-display.service
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/display/revision
journalctl -u inkpi-api.service -u inkpi-display.service \
  -u inkpi-network-helper.service --since '10 minutes ago'
```

Open `http://<pi-address>:8080/` and compare the Web eInk preview with the
physical panel. The installer confirms service startup but cannot assess
physical readability, ghosting, or waveform behavior.

For an extended hardware run:

```bash
bash scripts/hardware_24h_test.sh --hours 24
```

### Remove services

```bash
sudo bash deploy/uninstall_pi.sh
```

The uninstaller removes only the active unit files. SQLite data, environment
files, browser assets, source checkout, and unit backups are preserved.

## Ubuntu host agent

### Requirements

- Supported Ubuntu x86-64 or ARM64 system with systemd
- Python 3.12 and `uv` installed for the service user
- Network access to the Pi API
- Codex CLI installed and authenticated for Codex usage reports
- GitHub token when private contribution data is required

The frontend, Bun, Chromium, and Raspberry Pi GPIO dependencies are not needed
on the Ubuntu host.

### Configure and install

```bash
cd /path/to/InkPi
install -d -m 700 ~/.config/inkpi
install -m 600 deploy/env/host-agent.env.example ~/.config/inkpi/host-agent.env
${EDITOR:-nano} ~/.config/inkpi/host-agent.env
sudo bash deploy/install_host_agent.sh
```

The enrollment token must match `INKPI_AGENT_ENROLLMENT_TOKEN` in the Pi's
`api.env`. The installer syncs the backend environment, renders the service to
use the stable virtualenv executable, enables it, and confirms that it remains
active.

After the first successful registration, remove
`INKPI_AGENT_ENROLLMENT_TOKEN` from `host-agent.env` and restart the service.
The saved `~/.config/inkpi/host-agent.json` credential is used afterward.

### Verify the host agent

```bash
systemctl status inkpi-host-agent.service
journalctl -u inkpi-host-agent.service -f
curl -fsS http://inkpi.local:8080/api/reports/latest
```

### Remove the host service

```bash
sudo bash deploy/uninstall_host_agent.sh
```

The uninstaller preserves the host credential, environment file, checkout, and
unit backups.
