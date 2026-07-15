# Deployment Guide

This guide covers deploying InkPi to a Raspberry Pi 4B target device.

本指南说明如何将 InkPi 部署到 Raspberry Pi 4B 目标设备。

Deploy target: `meta_pi:/home/meta/Workspace/InkPi`
Target hardware: Waveshare 4.26" 800x480 4-gray e-ink HAT

部署目标：`meta_pi:/home/meta/Workspace/InkPi`
目标硬件：Waveshare 4.26" 800x480 4-gray e-ink HAT

## Prerequisites

| Item | Requirement |
|------|-------------|
| Device | Raspberry Pi 4B |
| OS | Raspberry Pi OS (Bookworm) |
| Python | 3.12 |
| Package Manager | `uv` |
| Network | SSH reachable (`ssh meta_pi`) |
| Display | Waveshare 4.26" e-ink HAT (SPI/GPIO) |

## Deployment Steps

### 1. Synchronize Repository

Use `rsync` to push code to the target device:

使用 `rsync` 将代码同步到目标设备：

```bash
rsync -avz --delete \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.ruff_cache' \
  --exclude='tmp/' \
  --exclude='.git' \
  --exclude='dist/' \
  --exclude='.lgd-*' \
  ./ meta_pi:/home/meta/Workspace/InkPi/
```

!!! warning "rsync Exclusions"
    You must exclude `.venv`, `__pycache__`, `.ruff_cache`, `tmp/`, `.git`, `dist/`, and `.lgd-*` GPIO runtime FIFOs. Skipping these exclusions causes slow syncs or conflicts.

    必须排除 `.venv`、`__pycache__`、`.ruff_cache`、`tmp/`、`.git`、`dist/` 和 `.lgd-*` GPIO 运行时 FIFO。不排除这些会导致同步缓慢或冲突。

### 2. Install Dependencies

```bash
ssh meta_pi
cd ~/Workspace/InkPi
uv sync --extra rpi
```

The `rpi` extra contains GPIO/SPI dependencies (`RPi.GPIO`, `spidev`, etc.) and should only be installed on the Pi.

`rpi` extra 包含 GPIO/SPI 依赖（`RPi.GPIO`、`spidev` 等），只在 Pi 上安装。

### 3. Configure Secrets

Create the admin token file:

创建 admin token 文件：

```bash
mkdir -p ~/.config/inkpi
printf 'INKPI_ADMIN_TOKEN=%s\n' 'replace-with-a-local-token' > ~/.config/inkpi/admin.env
chmod 600 ~/.config/inkpi/admin.env
```

!!! danger "File Permissions"
    `admin.env` must have `chmod 600`. This file holds the admin portal mutation token.

    `admin.env` 必须设置 `chmod 600`。该文件包含 admin portal 的 mutation token。

If you need API secrets, create a `.env` file in the project root:

如果需要 API secrets，在项目根目录创建 `.env` 文件：

```bash
# .env (do NOT commit this file)
EINK_GITHUB_API_KEY=ghp_xxxxxxxxxxxx
EINK_WEATHER_API_KEY=your-open-meteo-key
```

### 4. Configure Runtime

Copy the example config and adjust as needed:

复制示例配置并根据需要修改：

```bash
mkdir -p ~/.config/inkpi
cp config/inkpi.example.json ~/.config/inkpi/config.json
```

Edit `~/.config/inkpi/config.json` to adjust:

编辑 `~/.config/inkpi/config.json` 调整：

- `dashboard.rotation_interval_seconds` ... page rotation interval (页面轮转间隔)
- `dashboard.pages` ... enabled page list (启用的页面列表)
- `display.max_partial_refreshes` ... partial refresh upper limit (partial 刷新上限)
- `github.username` / `github.organization` ... GitHub user and org (GitHub 用户和组织)
- `weather.location` / `weather.timezone` ... weather location (天气位置)

### 5. Install Systemd Services

```bash
sudo bash scripts/systemd/install_inkpi_services.sh
```

The installer will:

安装器会：

- Create `inkpi-display.service`, `inkpi-core.service`, `inkpi-admin.service`
- Disable the legacy `eink-dashboard.service` if it exists (禁用 legacy `eink-dashboard.service`)
- Enable and start all three services (启用并启动三个服务)

!!! danger "Legacy Service Conflict"
    **Never** run the legacy `eink-dashboard.service` alongside `inkpi-display`. Both try to access SPI/GPIO, causing conflicts and panel corruption. The installer disables the legacy service automatically.

    **永远不要**同时运行 legacy `eink-dashboard.service` 和 `inkpi-display`。两者都会尝试访问 SPI/GPIO，导致冲突和面板损坏。安装器会自动禁用 legacy 服务。

### 6. Verify Deployment

```bash
systemctl status inkpi-display.service inkpi-core.service inkpi-admin.service
```

## Service Management

### Check Status

```bash
# All services (所有服务)
systemctl status inkpi-display.service inkpi-core.service inkpi-admin.service

# Single service (单个服务)
systemctl status inkpi-display.service
```

### Restart Services

```bash
# Restart all (重启所有)
sudo systemctl restart inkpi-display inkpi-core inkpi-admin

# Restart one (重启单个)
sudo systemctl restart inkpi-core
```

!!! note "Restart Order"
    If you need to restart everything, the recommended order is: display, then core, then admin. `inkpi-core` depends on the `inkpi-display` socket, and `inkpi-admin` depends on the `inkpi-core` socket.

    如果需要全部重启，建议顺序：display → core → admin。`inkpi-core` 依赖 `inkpi-display` 的 socket，`inkpi-admin` 依赖 `inkpi-core` 的 socket。

### Stop Services

```bash
sudo systemctl stop inkpi-admin inkpi-core inkpi-display
```

## Validation Commands

### Journal Logs

```bash
# Logs from the last 10 minutes (最近 10 分钟的日志)
journalctl -u inkpi-display.service -u inkpi-core.service -u inkpi-admin.service \
  --since "10 minutes ago"

# Display service only (只看 display 服务)
journalctl -u inkpi-display.service -f

# Errors only (只看错误)
journalctl -u inkpi-core.service -p err --since "1 hour ago"
```

### inkpi-ctl

```bash
# Check service status (查看服务状态)
uv run inkpi-ctl status

# List pages (列出页面)
uv run inkpi-ctl pages

# Control pages (控制页面)
uv run inkpi-ctl page codex_usage disable
uv run inkpi-ctl page codex_usage enable
```

### Physical Display Check

Confirm the physical screen shows both pages during the rotation cycle. The Codex page requires an installed and logged-in Codex CLI. Without it, the page should show an unavailable state without affecting the service.

确认物理显示屏在轮转周期内显示两个页面。Codex 页面需要已安装并登录的 Codex CLI；如果没有，页面应显示 unavailable 状态而不影响服务。

### Admin Portal Check

Confirm the admin portal is reachable on port `8081` at the expected LAN or hotspot address. Mutation routes require the token from `~/.config/inkpi/admin.env`.

确认 admin portal 在预期的 LAN 或 hotspot 地址的 `8081` 端口可达。Mutation 路由需要 `~/.config/inkpi/admin.env` 中的 token。

```bash
# Test from Pi locally (从 Pi 本地测试)
curl http://127.0.0.1:8081/api/status

# Test from LAN (从 LAN 测试)
curl http://<pi-ip>:8081/api/status
```

## Environment Files

### .env

The `.env` file in the project root holds API secrets. `load_config()` reads `.env` before loading the JSON config.

项目根目录的 `.env` 文件保存 API secrets。`load_config()` 在加载 JSON 配置前会先读取 `.env`。

| Variable | Description |
|----------|-------------|
| `EINK_GITHUB_API_KEY` | GitHub API token |
| `EINK_GITHUB_TOKEN` | GitHub API token (fallback) |
| `EINK_WEATHER_API_KEY` | Open-Meteo API key |

### admin.env

`~/.config/inkpi/admin.env` holds the admin portal token. The systemd service loads it via `EnvironmentFile`.

`~/.config/inkpi/admin.env` 保存 admin portal token。systemd service 通过 `EnvironmentFile` 加载。

| Variable | Description |
|----------|-------------|
| `INKPI_ADMIN_TOKEN` | Admin mutation token |

### Runtime Environment

The systemd services also use these environment variables, configured by the installer:

systemd service 还使用以下环境变量（由安装器配置）：

| Variable | Default | Description |
|----------|---------|-------------|
| `INKPI_DISPLAY_SOCKET` | `/run/inkpi-display/display.sock` | Display IPC socket |
| `INKPI_CORE_SOCKET` | `/run/inkpi-core/core.sock` | Core IPC socket |
| `INKPI_CONFIG` | `~/.config/inkpi/config.json` | Config file path (配置文件路径) |

## Hardware 24h Test

After deployment, run a 24-hour hardware test to validate long-term stability:

部署后建议运行 24 小时硬件测试，验证长期稳定性：

```bash
# Monitor logs for errors (监控日志中的错误)
watch -n 60 'journalctl -u inkpi-display.service -u inkpi-core.service \
  --since "24 hours ago" -p err --no-pager | tail -20'
```

Things to check:

检查要点：

| Item | Expected |
|------|----------|
| Display healthy | `true` |
| Consecutive failures | `0` |
| Full refreshes | Reasonable count: startup + page switches + periodic (合理数量：启动 + 页面切换 + 定期) |
| Partial refreshes | Majority (占多数) |
| Skipped refreshes | Present when nothing changed (存在，无变化时) |
| Admin portal | Continuously reachable (持续可达) |

```bash
# Check display status (检查 display 状态)
uv run inkpi-ctl status
```

## Troubleshooting

### Display Not Updating

```bash
# Check display service status (检查 display 服务状态)
systemctl status inkpi-display.service
journalctl -u inkpi-display.service --since "5 minutes ago"

# Check if core is submitting frames (检查 core 是否在提交帧)
journalctl -u inkpi-core.service --since "5 minutes ago" | grep "display action"
```

### Socket Permission Errors

```bash
# Check socket directories (检查 socket 目录)
ls -la /run/inkpi-display/
ls -la /run/inkpi-core/

# systemd-tmpfiles recreates these directories on reboot.
# If they don't exist, restarting the service creates them automatically.
# systemd-tmpfiles 会在重启后重建这些目录。
# 如果目录不存在，重启服务会自动创建。
```

### Legacy Service Conflict

```bash
# Check if the legacy service still exists (检查 legacy 服务是否还在)
systemctl status eink-dashboard.service

# If it exists, disable it (如果存在，禁用它)
sudo systemctl disable --now eink-dashboard.service
```

### Admin Portal Unreachable

```bash
# Check admin service (检查 admin 服务)
systemctl status inkpi-admin.service

# Check port (检查端口)
ss -tlnp | grep 8081

# Check firewall (检查防火墙)
sudo iptables -L -n | grep 8081
```
