# InkPi

**Modular e-ink dashboard appliance for Raspberry Pi 4B**

**Raspberry Pi 4B 上的模块化 e-ink 仪表盘设备**

InkPi drives a Waveshare 4.26-inch 800x480 4-gray e-ink display through a multi-process architecture, delivering a desktop dashboard with weather, system stats, GitHub metrics, and Codex usage.

InkPi 驱动 Waveshare 4.26 英寸 800x480 四灰度墨水屏，以多进程架构提供天气、系统状态、GitHub 统计和 Codex 用量等信息的桌面仪表盘。

---

## Quick Links

| Document | Description |
|----------|-------------|
| [About](about.md) | Product overview, feature list, and roadmap |
| [Architecture](architecture.md) | Multi-process architecture, data flow, and display strategy |
| [Developer Guide](guides/developer-guide.md) | Development setup and extension guide |
| [Development Plan](development/plan.md) | Phase progress and test coverage |
| [Admin Portal Design](services/admin-portal-design.md) | Local admin portal design |

---

## What is InkPi

InkPi is a standalone appliance running on a Raspberry Pi 4B. Three systemd services work together: `inkpi-core` handles orchestration and configuration, `inkpi-display` exclusively owns the hardware panel, and `inkpi-admin` serves a LAN management portal. Dashboard pages submit complete 800x480 grayscale frames. The display engine picks the optimal refresh strategy through dirty-region analysis.

InkPi 是一个运行在 Raspberry Pi 4B 上的独立设备。三组 systemd 服务协同工作：`inkpi-core` 负责编排与配置，`inkpi-display` 独占硬件面板，`inkpi-admin` 提供局域网管理门户。Dashboard 页面以 800x480 灰度图像提交完整帧，由显示引擎根据脏区分析自动选择最优刷新策略。

The entire project is built with Python 3.12 and `uv`. All fonts are bundled inside the package, with zero system font dependencies.

整个项目使用 Python 3.12 和 `uv` 构建，字体全部内置于包内，不依赖系统字体。

---

## Quick Start

```bash
# Install dev dependencies (安装开发依赖)
uv sync --extra dev

# Run tests, currently 101 (运行测试)
uv run pytest -q

# Render the Overview page preview (渲染 Overview 页面预览)
uv run inkpi-preview overview --mock-data --output tmp/overview.png

# E-ink dithered preview, 4-gray Floyd-Steinberg (e-ink 抖动预览)
uv run inkpi-preview overview --mock-data --eink-preview --output tmp/overview_eink.png
```

### Run Services Locally (本地运行服务)

```bash
# Start the display service (启动 display 服务)
INKPI_DISPLAY_SOCKET=/tmp/inkpi-display.sock uv run inkpi-display

# Start the core service (启动 core 服务)
INKPI_DISPLAY_SOCKET=/tmp/inkpi-display.sock \
INKPI_CORE_SOCKET=/tmp/inkpi-core.sock \
uv run inkpi-core

# Query page status (查询页面状态)
uv run inkpi-ctl --socket /tmp/inkpi-core.sock pages

# Start the admin portal (启动 admin 门户)
uv run inkpi-admin --core-socket /tmp/inkpi-core.sock
```

---

## Project Structure

```
inkpi/
├── core.py          # Orchestration, scheduling, and config management (编排调度与配置管理)
├── display/         # Display engine and refresh policy, sole hardware owner (显示引擎与刷新策略，唯一硬件所有者)
├── dashboard/       # Dashboard pages and data services (Dashboard 页面与数据服务)
├── management/      # System and network facts (系统与网络状态)
├── admin/           # Local web admin portal (本地 Web 管理门户)
├── contracts.py     # Versioned cross-process contracts (版本化跨进程契约)
├── ipc.py           # Unix socket IPC transport (Unix socket IPC 传输)
├── ui/              # Rendering and fonts (渲染与字体)
└── fonts/           # Bundled fonts, 7 TTF files (内置字体，7 个 TTF)
```
