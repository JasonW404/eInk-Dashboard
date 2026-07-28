# Deployment Guide

InkPi is deployed from prebuilt, architecture-specific release archives.
Install the cloud control plane first, publish it over HTTPS, then connect the
Raspberry Pi display client. Python, `uv`, and Bun are build-time dependencies
used by CI; they are not required on either deployment target.

## Select a release archive

Choose the archive matching the role and `uname -m`:

| Role | `x86_64` | `aarch64` |
|---|---|---|
| Cloud | `inkpi-cloud-<version>-linux-amd64.tar.gz` | `inkpi-cloud-<version>-linux-arm64.tar.gz` |
| Display | `inkpi-display-<version>-linux-amd64.tar.gz` | `inkpi-display-<version>-linux-arm64.tar.gz` |

Download the archive and `SHA256SUMS` from the GitHub release, then verify it:

```bash
sha256sum --check SHA256SUMS --ignore-missing
```

## Cloud control plane

### Requirements

- Debian 13, Ubuntu, or another systemd-based 64-bit Linux host
- Recommended minimum: 2 vCPU, 2 GB RAM, 8 GB disk
- An HTTPS reverse proxy in front of port 8080
- Debian's `chromium` package; the installer adds it automatically when absent

Extract and run the bundled installer:

```bash
tar xzf inkpi-cloud-<version>-linux-amd64.tar.gz
cd inkpi-cloud-<version>-linux-amd64
sudo ./install.sh
```

On the first run, the installer interactively requests the admin, display, and
HostAgent enrollment tokens. Input is hidden and written directly to the
root-owned `0600` file `/etc/inkpi/cloud.env`; tokens are not passed through
process arguments. Use independent random values for each prompt.

The installer then installs the immutable release under
`/opt/inkpi/cloud/<version>-<architecture>`, switches the `current` symlink,
and enables `inkpi-cloud.service`. The installer always creates and uses the
dedicated `inkpi` system account; its identity cannot be overridden.

To replace the saved tokens later:

```bash
sudo ./install.sh --reconfigure
```

The bundled installer targets systemd hosts, including Debian LXC containers.
For a minimal Docker image without systemd, copy the same standalone directory
into the image, create an `inkpi` user in the Dockerfile, and run
`inkpi-cloud/inkpi-api` directly as that user. Do not run the application
process itself as root.

Verify locally:

```bash
systemctl status inkpi-cloud.service
curl -fsS http://127.0.0.1:8080/api/health
journalctl -u inkpi-cloud.service --since '10 minutes ago'
```

Publish port 8080 through an HTTPS reverse proxy. Do not expose it as plain HTTP
over an untrusted network because the Pi bearer token accompanies requests.

## Raspberry Pi display client

### Requirements

- Raspberry Pi 4B with a 64-bit ARM Linux installation
- Waveshare 4.26-inch 800×480 HAT
- Network access to the cloud HTTPS endpoint

Bun, Chromium, Python, `uv`, a database, and NetworkManager control are not
required. Extract the ARM64 display bundle:

```bash
tar xzf inkpi-display-<version>-linux-arm64.tar.gz
cd inkpi-display-<version>-linux-arm64
sudo ./install.sh
```

On its first run, the installer interactively asks for the public cloud API URL
and the exact display token entered during cloud installation. The token is
hidden while typing and saved to root-owned
`/etc/inkpi/pi-display.env`. It then installs under
`/opt/inkpi/display/<version>-arm64` and enables `inkpi-display.service`.

To change the cloud URL or token:

```bash
sudo ./install.sh --reconfigure
```

Verify:

```bash
systemctl status inkpi-display.service
journalctl -u inkpi-display.service --since '10 minutes ago'
```

Logs can prove that a frame was downloaded and accepted, but they cannot prove
physical readability, ghosting, or waveform quality. Confirm those visually on
the panel.

## Optional HostAgent

The HostAgent binary is included in every cloud archive. Enable and configure
it while installing the cloud role:

```bash
sudo ./install.sh \
  --enable-host-agent \
  --host-agent-api-url http://127.0.0.1:8080 \
  --host-agent-name homelab-cloud
```

The URL and name are non-secret command-line parameters. The installer copies
the enrollment token internally from the protected cloud configuration, waits
for registration credentials, removes the enrollment token from the HostAgent
environment, and restarts the service. Secrets are never passed in process
arguments. When HostAgent is enabled from an interactive terminal, the
installer also offers a hidden optional prompt for a GitHub API token used for
private contribution data.

Omit `--enable-host-agent` when report collection is not needed. The binary is
installed with the cloud release, but its systemd service remains disabled.

For unattended installation, pre-create `/etc/inkpi/cloud.env` or
`/etc/inkpi/pi-display.env` as `root:root` with mode `0600`. Interactive
prompting is skipped when a valid file already exists.

## Removal

Run `sudo ./uninstall.sh` from the corresponding extracted release directory.

The uninstallers preserve protected configuration and application data.

## Building releases

Normal deployments should use published binaries. Maintainers can reproduce
native binaries with Python 3.12, `uv`, Bun, and PyInstaller:

```bash
cd backend && uv sync --extra dev --extra rpi && cd ..
cd frontend && bun install --frozen-lockfile && bun run build && cd ..
bash packaging/build_binaries.sh
```

PyInstaller output is architecture-specific. Build ARM64 binaries on an ARM64
Linux runner rather than attempting to cross-compile them on amd64.
