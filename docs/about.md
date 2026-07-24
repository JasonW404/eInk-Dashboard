# About InkPi

## Product Overview

InkPi is a modular e-ink dashboard appliance running on Raspberry Pi 4B, driving a Waveshare 4.26-inch 800x480 4-gray e-ink HAT. It uses a multi-process architecture with Unix socket IPC and a longevity-first refresh policy designed to extend panel lifespan.

InkPi 是运行在 Raspberry Pi 4B 上的模块化 e-ink 仪表盘设备，驱动 Waveshare 4.26 英寸 800x480 四灰度墨水屏。采用多进程架构，通过 Unix socket 进行进程间通信，以 longevity-first 刷新策略延长面板寿命。

| Property | Value |
|----------|-------|
| Target Hardware | Raspberry Pi 4B + Waveshare 4.26" e-ink HAT |
| Resolution | 800x480, 4 gray levels |
| Runtime | Python 3.12, multi-process (systemd managed) |
| Package Manager | uv + pyproject.toml |
| Deploy Target | `meta_pi:/home/meta/Workspace/InkPi` |
| Current Version | 0.2.0 |

---

## Feature Summary

### Runtime Services

| Service | CLI Entry | Responsibility | Status |
|---------|-----------|----------------|--------|
| **inkpi-core** | `inkpi-core` | Orchestration, config management, page rotation, service coordination (编排调度、配置管理、页面轮转、服务协调) | ✅ Running |
| **inkpi-display** | `inkpi-display` | Sole SPI/GPIO owner, refresh policy decisions, panel lifecycle (唯一 SPI/GPIO 持有者、刷新策略决策、面板生命周期) | ✅ Running |
| **inkpi-admin** | `inkpi-admin` | Local web admin portal on LAN/hotspot, port 8081 (本地 Web 管理门户) | ✅ Running |
| **inkpi-ctl** | `inkpi-ctl` | Query and control a running core service (查询和控制运行中的 core 服务) | ✅ Available |
| **inkpi-preview** | `inkpi-preview` | Render pages to PNG without display hardware (渲染页面为 PNG，无需显示硬件) | ✅ Available |

### Dashboard Pages

| Page | page_id | Content | Status |
|------|---------|---------|--------|
| **Overview** | `overview` | Weather, system load, GitHub stats, Codex usage, knowledge cards (天气、系统负载、GitHub 统计、Codex 用量、知识卡片) | ✅ Registered |
| **Codex Usage** | `codex_usage` | Standalone Codex subscription usage page (Codex 订阅用量独立页面) | ⏳ Panel implemented, not yet a standalone page |

### Data Sources

| Service | Source | Degradation Strategy | Status |
|---------|--------|----------------------|--------|
| Weather | Open-Meteo API | Returns degraded snapshot | ✅ |
| GitHub Stats | GitHub REST API | Returns degraded snapshot | ✅ |
| System Resources | `/proc/stat` + `/proc/meminfo` | macOS falls back to os.sysconf | ✅ |
| Network Status | `/sys/class/net` + `iwgetid` | macOS falls back to socket | ✅ |
| Knowledge Cards | Local JSON + remote URL | Local first, remote override | ✅ |
| Codex Usage | `codex app-server` subprocess | Shows unavailable state | ✅ |
| Date/Time | System clock + configured timezone | No external dependency | ✅ |

### Display Engine

| Feature | Description | Status |
|---------|-------------|--------|
| Refresh Policy | Longevity-first: startup/page_change/grayscale/large triggers full, rest goes partial (longevity-first：startup/page_change/grayscale/large 触发全刷，其余走 partial) | ✅ |
| Dirty-Region Analysis | ImageChops diff detection + 8px alignment + region padding | ✅ |
| Region Tracking | _RegionTracker counts partials per region, triggers repair at threshold (按区域计数 partial，达到阈值触发 repair) | ✅ |
| Frame Queue | Serialized single-thread worker, maxsize=1, normal frames coalesce (序列化单线程 worker，normal 帧可被替换) | ✅ |
| Failure Recovery | Re-initialize after consecutive failures, clear frame history (连续失败后重新初始化，清除帧历史) | ✅ |
| Panel Sleep | Panel enters deep sleep on service shutdown (服务关闭时进入深度睡眠) | ✅ |
| Simulation Mode | Auto-enabled without hardware, all ops log + return True (无硬件时自动进入) | ✅ |
| FileBackend | Writes each frame to PNG for offline refresh debugging (将每帧写入 PNG 文件) | ✅ |
| 4-Gray Support | 4-gray initialization + getbuffer_4Gray + display_4Gray | ✅ |
| Region Partial | display_Partial_Region for partial refresh | ✅ |

---

## Admin Portal

`inkpi-admin` runs as a third systemd service, binding port 8081 and serving a local management interface over LAN or hotspot.

`inkpi-admin` 在 systemd 部署中作为第三个服务运行，绑定端口 8081，通过 LAN 或热点网络提供本地管理界面。

| Feature | Description | Status |
|---------|-------------|--------|
| Status API | `/api/status` returns combined JSON snapshot | ✅ |
| Dashboard Preview | `/api/dashboard/preview/{page_id}.png` renders mock preview | ✅ |
| Page Control | Enable/disable dashboard pages, delegated to core contracts (启用/禁用 dashboard 页面) | ✅ |
| Network Ops Queue | Wi-Fi connect, hotspot enable, etc. queued in memory (网络操作排入内存队列) | ✅ Queue only |
| Authentication | X-InkPi-Admin-Token / Bearer Token | ✅ |
| CORS Protection | Rejects cross-origin browser requests (拒绝跨域浏览器请求) | ✅ |
| Event Log | Bounded, sanitized operation event stream at `/api/events` (有界、脱敏的操作事件流) | ✅ |
| Network Policy | Pure decision layer (network_policy.py), no shell/NM execution (纯决策层，不执行 shell/NM 操作) | ✅ |
| Network Helper | nmcli command planning with dry-run, no actual execution (nmcli 命令计划，不实际执行) | ✅ |
| NetworkManager Integration | Privileged executor, actual nmcli calls (特权执行器，实际调用 nmcli) | ❌ Not implemented |
| Portal UI Polish | Currently basic HTML, needs UX refinement (当前为基础 HTML，需完善交互体验) | ❌ Not implemented |

!!! note
    Privileged NetworkManager operations are delegated to a narrow-scope helper. They never execute inside dashboard, core, or admin UI code. This keeps portal requests responsive and prevents display refresh from blocking system configuration.

    特权 NetworkManager 操作被委托给窄范围 helper，不会在 dashboard、core 或 admin UI 代码中执行。这保证了门户请求的响应性，也防止显示刷新阻塞系统配置。

---

## Infrastructure

| Item | Description | Status |
|------|-------------|--------|
| IPC | Versioned JSON-over-Unix-socket (CONTRACT_VERSION=1) | ✅ |
| Config Persistence | Atomic writes of versioned JSON at `~/.config/inkpi/config.json` (原子写入版本化 JSON) | ✅ |
| Secret Management | `.env` files, never in JSON config/logs/tests/docs (密钥不进入 JSON 配置/日志/测试/文档) | ✅ |
| systemd Deployment | 3 service files + install script (3 个 service 文件 + 安装脚本) | ✅ |
| Bundled Fonts | 7 TTF files in `inkpi/fonts/`, loaded via `importlib.resources` | ✅ |
| No System Fonts | Architecture tests forbid `/usr/share/fonts` and similar paths (架构测试强制禁止系统字体路径) | ✅ |
| E-Ink Dither Preview | `--eink-preview` flag, 4-gray Floyd-Steinberg quantization | ✅ |
| GitHub Actions CI | test (macOS+Ubuntu) + lint (ruff) + smoke (dual-service) | ✅ |
| Ruff Static Analysis | dev deps + CI lint job | ✅ |
| Structural Render Tests | Size/mode/content/grayscale distribution assertions, replaces golden images (尺寸/模式/内容/灰度分布断言) | ✅ |
| smoke_test.sh | Scripted dual-service smoke test (脚本化双服务冒烟测试) | ✅ |

---

## Test Coverage

Currently **101 tests** across **18 test files**.

当前共 **101 个测试**，分布在 **18 个测试文件**中。

| Test File | Count | Coverage |
|-----------|-------|----------|
| `test_admin_server.py` | 9 | HTTP routes, auth, CORS, page control, network ops |
| `test_admin_network_policy.py` | 7 | Network access policy decisions (offline/ethernet/Wi-Fi/hotspot) |
| `test_admin_network_helper.py` | 5 | nmcli command planning (Wi-Fi scan/connect/hotspot/password rotation) |
| `test_admin_service.py` | 4 | AdminService snapshot composition, page control, event logging |
| `test_admin_portal.py` | 3 | Portal structure, network/dashboard operation zones |
| `test_admin_auth.py` | 4 | Auth strategies (unconfigured/match/cross-origin/Bearer) |
| `test_admin_events.py` | 2 | Event log sanitization and bounded capacity |
| `test_admin_preview.py` | 2 | Mock preview PNG rendering and unknown page rejection |
| `test_admin_systemd.py` | 2 | systemd installer and service templates |
| `test_inkpi_display_engine.py` | 7 | Refresh decisions, partial limits, skip, frame coalesce, failure recovery, region repair |
| `test_inkpi_core_contracts.py` | 5 | Non-blocking control, management contracts, architecture boundaries, socket isolation |
| `test_inkpi_config_and_dashboard.py` | 4 | Atomic config writes, page enable/disable/idempotent/last-page rejection |
| `test_services.py` | 4 | Weather/GitHub/knowledge card services (fake adapter injection) |
| `test_file_backend.py` | 13 | FileBackend all methods, counters, directory creation |
| `test_font_architecture.py` | 10 | No-system-font policy, bundled font existence and loadability |
| `test_rendering_structure.py` | 8 | Render output size/mode/content/grayscale distribution |
| `test_eink_preview.py` | 6 | 4-gray dithered output size/mode/palette/white/black |
| `test_aggregation_and_bootstrap.py` | 2 | DashboardDataService snapshot assembly, bootstrap wiring |
| `test_cli_preview.py` | 1 | `inkpi-preview --mock-data` skips live collect |

### Coverage Gaps

| Gap | Priority | Description |
|-----|----------|-------------|
| IPC Transport Layer | 🟡 Medium | `inkpi/ipc.py` serve/request lacks direct tests (`inkpi/ipc.py` 的 serve/request 无直接测试) |
| codex_usage Page | 🟡 Medium | Standalone page not yet implemented, no dedicated panel render tests (独立页面未实现) |
| inkpi-ctl CLI | 🟢 Low | `control_main()` has no tests |
| Config Validation Edge Cases | 🟢 Low | Malformed JSON, unknown fields, version migration not covered (畸形 JSON、未知字段、版本迁移未覆盖) |
| Admin Portal UI | 🟢 Low | HTML render has structural tests only, no E2E (HTML 渲染仅有结构测试，无 E2E) |

---

## Roadmap

### Near-term

| Item | Description | Priority |
|------|-------------|----------|
| codex_usage Standalone Page | Register CodexPanel as a standalone dashboard page with rotation support (将 CodexPanel 注册为独立 dashboard 页面，支持轮转) | 🟡 Medium |
| API Production Hardening | Rate limiting, caching, retries, batch request optimization (限流、缓存、重试、批量请求优化) | 🟡 Medium |
| IPC Transport Tests | Direct coverage of `inkpi/ipc.py` serve/request | 🟡 Medium |
| 24h Hardware Test | Run on meta_pi to validate stability (在 meta_pi 上运行验证稳定性) | 🟡 Medium |

### Mid-term

| Item | Description | Priority |
|------|-------------|----------|
| NetworkManager Integration | Privileged executor for actual nmcli network operations (特权执行器，实际调用 nmcli 执行网络操作) | 🟡 Medium |
| Admin Portal UI Polish | Refine interaction experience and responsive design (完善交互体验与响应式设计) | 🟡 Medium |
| Config Migration | Automatic migration on schema version upgrades (schema version 升级时的自动迁移) | 🟢 Low |
| Multi-Page Support | Add more dashboard pages like calendar, TODO, custom cards (新增更多 dashboard 页面) | 🟢 Low |

### Future

| Item | Description |
|------|-------------|
| Hotspot Network Mode | Pi acts as a Wi-Fi hotspot, users configure via phone browser (Pi 作为 Wi-Fi 热点，用户通过手机浏览器配置) |
| OTA Updates | Automatic or manual InkPi software updates (自动或手动更新 InkPi 软件) |
| Remote Management | Manage multiple devices through cloud or LAN (通过云端或局域网远程管理多台设备) |
| Plugin System | Third-party dashboard page plugin mechanism (第三方 dashboard 页面插件机制) |
