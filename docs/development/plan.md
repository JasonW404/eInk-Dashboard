# InkPi Development Plan

> This page indexes all InkPi development work.
> 本文档是 InkPi 全部开发工作的索引页面。
>
> Architecture design: [Architecture](../architecture.md).
> 架构设计见 [Architecture](../architecture.md)。
>
> Developer conventions: [Developer Guide](../guides/developer-guide.md).
> 开发规范见 [Developer Guide](../guides/developer-guide.md)。

---

## Product Overview

InkPi is a modular e-ink dashboard appliance running on Raspberry Pi 4B,
driving a Waveshare 4.26-inch 800x480 4-gray e-ink HAT.
It uses a multi-process architecture (多进程架构) with Unix socket IPC.

InkPi 是运行在 Raspberry Pi 4B 上的模块化 e-ink 仪表盘设备，
驱动 Waveshare 4.26 英寸 800x480 四灰度墨水屏。
采用多进程架构，通过 Unix socket 进行进程间通信。

| Property | Value |
|----------|-------|
| Target Hardware | Raspberry Pi 4B + Waveshare 4.26" e-ink HAT |
| Resolution | 800x480, 4-level grayscale |
| Runtime | Python 3.12, multi-process (systemd managed) |
| Package Manager | uv + pyproject.toml |
| Deploy Target | `meta_pi:/home/meta/Workspace/InkPi` |
| Current Version | 0.2.0 |
| Test Coverage | 182 tests across 27 test files |

---

## Phase Overview

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| Phase 0 | Foundation | ✅ Done | 文档框架、开发规范、Python 3.12 基线 |
| Phase 1 | Data Services | ✅ Done | 统一数据模型、可降级服务、数据调度器 |
| Phase 2 | UI + Display | ✅ Done | 固定布局渲染、EPD 适配、刷新策略引擎 |
| Phase 3 | Runtime Robustness | ✅ Done | 重试超时、故障隔离、架构边界测试 |
| Phase 4 | Cross-Platform CI | ✅ Done | FileBackend、e-ink 预览、GitHub Actions |
| Phase 5 | Font Bundling | ✅ Done | 字体内置、统一加载、无系统字体策略 |
| Phase 6 | Admin Portal | ✅ Done | Privileged helper, portal UI, session auth, staged Wi-Fi, NAT, live preview |

---

## Phase 0: Foundation ✅

Project initialization and infrastructure setup.
项目初始化与基础设施搭建。

**Deliverables:**

- Documentation framework and architecture docs (`docs/architecture.md`)
- Developer conventions (`.github/copilot-instructions.md`)
- Python 3.12 + uv baseline environment
- Configuration model and refresh strategy skeleton

---

## Phase 1: Data Services ✅

Build a unified data collection layer. All external data sources connect
through the provider protocol (服务契约层) with consistent error degradation.

构建统一的数据采集层，所有外部数据源通过 provider protocol 接入，
具备统一的错误降级能力。

**Deliverables:**

- Unified domain model (DashboardSnapshot and panel data models)
- Service contract layer (provider protocols)
- 6 degradable data services: GitHub / Weather / Time / System / Knowledge Card / Codex
- Data scheduler (DataScheduler, interval-based collection, non-blocking for control requests)

!!! success "Acceptance"
    任一 provider 不可用时，应用仍能渲染并刷新。服务层具备统一数据模型与错误降级返回。

!!! note "Deferred"
    生产级 API 细节 (限流、缓存、重试、批量请求优化) 移至未来路线图。

---

## Phase 2: UI + Display ✅

Implement the complete rendering pipeline and display driver layer,
from panel renderers to EPD hardware adaptation.

实现完整的渲染管线和显示驱动层，从面板渲染器到 EPD 硬件适配。

**Deliverables:**

- Fixed-layout rendering (800x480 landscape, 4-gray)
- Panel renderers: GitHub stats / Codex usage / sidebar / knowledge card
- EPD adaptation layer: full / partial / region refresh / 4-gray mode
- Dirty-region calculation and area tracking (ImageChops + 8px alignment)
- Refresh strategy engine (longevity-first policy, 7 scenarios)
- Frame queue and serialized worker
- Simulation mode (automatic fallback without hardware)
- `inkpi-preview` CLI preview tool

!!! success "Acceptance"
    局刷节奏稳定，全刷触发正确 (单元测试覆盖)。
    `inkpi-preview overview --mock-data` 可生成预览 PNG。

!!! note "Deferred"
    实机 24h 集成测试移至未来路线图。

---

## Phase 3: Runtime Robustness ✅

Harden runtime stability. Services must recover automatically under
fault conditions.

加固运行时稳定性，确保服务在异常条件下能自动恢复。

**Deliverables:**

- Retry and timeout policies (adapter-level timeout configuration)
- Runtime logging and key metrics (DisplayStatus / CoreStatus telemetry)
- Structured rendering tests (size / mode / content / gray distribution)
- Refresh strategy unit tests (7 scenarios)
- Automatic failure recovery (re-initialize after consecutive failures)
- Page fault isolation (core isolates failed pages, skips to next cycle)
- Architecture boundary tests (dashboard cannot import display hardware)

!!! success "Acceptance"
    关键模块覆盖基础单元测试，运行异常可自动恢复。

---

## Phase 4: Cross-Platform Verification & CI ✅

> Goal: complete 90% of verification on macOS dev machines.
> 目标: 在 macOS 开发机上完成 90% 的验证工作。

Solve the cross-platform verification gap between macOS development and
Pi deployment. See [Cross-Platform CI](archive/cross-platform-ci.md)
for the detailed requirements doc.

解决 macOS 开发、Pi 部署的跨平台验证难题。详细需求文档见
[Cross-Platform CI](archive/cross-platform-ci.md)。

**Deliverables:**

| Sub-task | File | Tests |
|----------|------|-------|
| FileBackend frame recorder | `inkpi/display/file_backend.py` | 13 |
| e-ink dithering preview | `inkpi/ui/eink_preview.py` | 6 |
| GitHub Actions CI | `.github/workflows/ci.yml` | - |
| smoke_test.sh | `scripts/smoke_test.sh` | - |
| ruff static analysis | `pyproject.toml [tool.ruff]` | - |
| Structured rendering tests | `tests/test_rendering_structure.py` | 8 |

!!! success "Acceptance"
    101 tests 全部通过，ruff clean，compileall clean。

---

## Phase 5: Font Bundling ✅

> Goal: eliminate system font dependencies and ensure cross-platform
> rendering consistency.
> 目标: 消除系统字体依赖，确保跨平台渲染一致性。

Move all fonts into the package, unify the loading entry point, and
guard against regressions with architecture tests. See
[Font Bundling](archive/font-bundling.md) for the detailed requirements doc.

将全部字体移入包内，统一加载入口，用架构测试防止回退。详细需求文档见
[Font Bundling](archive/font-bundling.md)。

**Deliverables:**

| Sub-task | Description |
|----------|-------------|
| Fonts moved into package | `assets/fonts/` migrated to `inkpi/fonts/` |
| New fonts added | Noto Emoji (emoji) |
| Unified loading | Only `_load_font()` in `drawing.py` remains, 5 duplicates removed |
| System fallback eliminated | All `/usr/share/fonts/` path references deleted |
| importlib.resources | Path resolution via `files("inkpi").joinpath("fonts")` |
| Architecture tests | System font paths forbidden (`test_font_architecture.py`, 10 tests) |

!!! success "Acceptance"
    7 个 TTF 文件全部内置，架构测试强制无系统字体策略。

---

## Phase 6: Admin Portal Implementation ✅

> Goal: complete the admin portal with privileged helper, portal UI,
> session auth, staged Wi-Fi, hidden hotspot/NAT, and live preview.
> 目标: 完成管理门户全部功能，包括特权 helper、门户 UI、session 认证、
> 分阶段 Wi-Fi、隐藏热点/NAT 和实时预览。

**Deliverables:**

| Sub-task | File | Tests |
|----------|------|-------|
| Privileged helper backend | `inkpi/admin/helper_client.py`, `inkpi/admin/privileged.py` | 21 |
| Live preview contract | `inkpi/core.py`, `inkpi/admin/preview.py` | 7 |
| Portal UI split (6 pages) | `inkpi/admin/server.py` | - |
| Service layer wiring | `inkpi/admin/service.py`, `inkpi/admin/operations.py` | 17 |
| Staged Wi-Fi flow | `inkpi/admin/server.py`, `inkpi/admin/service.py` | 8 |
| Hidden hotspot + NAT | `inkpi/admin/network_helper.py`, `inkpi/admin/privileged.py` | 14 |
| Session auth + CSRF | `inkpi/admin/auth.py`, `inkpi/admin/events.py` | 14 |

!!! success "Acceptance"
    182 tests 全部通过，ruff clean，compileall clean。
    管理门户 11 个模块全部实现，6 个页面可用。

---

## Future Roadmap

### Near Term

| Item | Description | Priority |
|------|-------------|----------|
| codex_usage standalone page | 将 CodexPanel 注册为独立 dashboard 页面，支持轮转 | 🟡 Medium |
| API production hardening | 限流、缓存、重试、批量请求优化 | 🟡 Medium |
| IPC transport tests | `inkpi/ipc.py` serve/request 直接覆盖 | 🟡 Medium |
| 24h hardware test | 在 meta_pi 上运行 `hardware_24h_test.sh` 验证稳定性 | 🟡 Medium |
| Privileged helper deployment | 在 meta_pi 上部署并验证 helper 进程 IPC | 🟡 Medium |
| Cookie session wiring | 将 session auth 接入 server.py 路由中间件 | 🟡 Medium |
| Admin portal UI polish | 6 个页面已实现，需完善交互体验与响应式设计 | 🟡 Medium |

### Mid Term

| Item | Description | Priority |
|------|-------------|----------|
| Config migration | schema version 升级时的自动迁移 | 🟢 Low |

### Long Term

| Item | Description |
|------|-------------|
| Hotspot network mode | Pi 作为 Wi-Fi 热点，用户通过手机浏览器配置 |
| OTA updates | 自动或手动更新 InkPi 软件 |
| Remote management | 通过云端或局域网远程管理多台设备 |
| Plugin system | 第三方 dashboard 页面插件机制 |

---

## Test Coverage

Currently **182 tests** across 27 test files.
当前共 **182 个测试**，分布在 27 个测试文件中。

| Test File | Count | Scope |
|-----------|-------|-------|
| `test_admin_server.py` | 9 | HTTP routes, auth, CORS, page controls, network operations |
| `test_admin_network_policy.py` | 10 | Network access policy decisions (offline/ethernet/Wi-Fi/hotspot) |
| `test_admin_network_helper.py` | 5 | nmcli command planning (Wi-Fi scan/connect/hotspot/password rotation) |
| `test_admin_service.py` | 4 | AdminService snapshot composition, page controls, event logging |
| `test_admin_portal.py` | 3 | Portal structure, network/dashboard operation zones |
| `test_admin_auth.py` | 4 | Auth policies (unconfigured/match/cross-origin/Bearer) |
| `test_admin_events.py` | 2 | Event log sanitization and bounded capacity |
| `test_admin_preview.py` | 2 | Mock preview PNG rendering and unknown page rejection |
| `test_admin_systemd.py` | 2 | systemd installer and service templates |
| `test_admin_operations.py` | 3 | Operation queue, mutation tracking |
| `test_helper_client.py` | 10 | HelperClient socket IPC, serialization, error handling |
| `test_privileged.py` | 11 | Privileged helper allowlist, secret stdin, command dispatch |
| `test_admin_service_integration.py` | 14 | AdminService end-to-end wiring, snapshot composition |
| `test_admin_staged_wifi.py` | 8 | Staged Wi-Fi connect/confirm/fail flow, recovery tracking |
| `test_hidden_hotspot.py` | 14 | Hidden hotspot, NAT/iptables rules, ip_forward, cleanup |
| `test_admin_session_auth.py` | 14 | Cookie sessions, CSRF tokens, SessionStore lifecycle |
| `test_admin_preview_live.py` | 7 | Live preview contract, base64 PNG transport, mock fallback |
| `test_inkpi_display_engine.py` | 7 | Refresh decisions, partial limits, skip, frame replacement, failure recovery, region repair |
| `test_inkpi_core_contracts.py` | 5 | Non-blocking control, admin contracts, architecture boundaries, socket independence |
| `test_inkpi_config_and_dashboard.py` | 4 | Atomic config writes, page enable/disable/idempotent/last-page rejection |
| `test_services.py` | 4 | Weather/GitHub/knowledge card services (fake adapter injection) |
| `test_file_backend.py` | 13 | FileBackend all methods, counters, directory creation |
| `test_font_architecture.py` | 10 | No-system-font policy, bundled font existence and loadability |
| `test_rendering_structure.py` | 8 | Render output size/mode/content/gray distribution |
| `test_eink_preview.py` | 6 | 4-gray dithering output size/mode/palette/white/black |
| `test_aggregation_and_bootstrap.py` | 2 | DashboardDataService snapshot assembly, bootstrap wiring |
| `test_cli_preview.py` | 1 | `inkpi-preview --mock-data` skips live collect |

### Coverage Gaps

| Gap | Priority | Description |
|-----|----------|-------------|
| IPC transport layer | 🟡 Medium | `inkpi/ipc.py` serve/request 无直接测试 |
| codex_usage page | 🟡 Medium | 独立页面未实现，面板渲染无专用测试 |
| inkpi-ctl CLI | 🟢 Low | `control_main()` 无测试 |
| Config validation edges | 🟢 Low | 畸形 JSON、未知字段、版本迁移未覆盖 |
| Admin portal E2E | 🟢 Low | 6 个页面已实现，无浏览器 E2E 测试 |
