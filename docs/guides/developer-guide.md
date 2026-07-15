# InkPi Developer Guide

This guide covers how to develop, test, extend, and deploy InkPi while keeping module ownership boundaries intact. Read [Architecture](../architecture.md) first for the runtime design, then check `AGENTS.md` in the project root for the current codebase status.

本指南说明如何开发、测试、扩展和部署 InkPi，同时保持模块所有权边界。先阅读 [Architecture](../architecture.md) 了解运行时设计，再阅读项目根目录的 `AGENTS.md` 了解当前代码库状态。

## Repository Layout

| Path | Description |
|------|-------------|
| `inkpi/core.py` | Main orchestration service and control request routing (主编排服务和控制请求路由) |
| `inkpi/admin/` | Local admin portal design primitives and network policy (本地管理门户设计原语和网络策略) |
| `inkpi/display/` | Standalone display service, refresh policy, hardware ownership (独立 display 服务、刷新策略、硬件所有权) |
| `inkpi/dashboard/` | Page protocol, registry, rotation, built-in pages (页面协议、注册表、轮转、内置页面) |
| `inkpi/management/` | System/network facts and future management foundation (系统/网络 facts 和未来管理基础) |
| `inkpi/contracts.py` | Versioned DTOs and cross-module protocols (版本化 DTO 和跨模块协议) |
| `inkpi/ipc.py` | JSON-over-Unix-socket transport layer |
| `inkpi/fonts/` | Bundled TTF fonts: MapleMono-CN, Noto Emoji (打包的 TTF 字体) |
| `inkpi/ui/` | Render panels, drawing utilities, font loading (渲染面板、绘图工具、字体加载) |
| `config/inkpi.example.json` | Non-secret runtime config example (非 secret 运行时配置示例) |
| `scripts/systemd/` | Service templates and deploy installer (服务模板和部署安装器) |
| `tests/` | Architecture and runtime tests (架构和运行时测试) |

## Ownership Rules

- Only `inkpi-display` may access SPI/GPIO or choose full / partial / skipped refresh.

  只有 `inkpi-display` 可以访问 SPI/GPIO 或选择 full / partial / skipped 刷新。

- Dashboard pages return complete `800x480` grayscale PIL images. They don't request refresh modes or import display implementations.

  Dashboard 页面返回完整的 `800x480` 灰度 PIL 图像。它们不请求刷新模式，不导入 display 实现。

- `inkpi-core` owns config persistence, scheduling, and service orchestration.

  `inkpi-core` 拥有配置持久化、调度和服务编排。

- Management owns system and network facts. Dashboard pages consume those facts through contracts.

  Management 拥有系统和网络 facts。Dashboard 页面通过 contracts 消费这些 facts。

- Cross-process and cross-module public behavior uses typed contracts from `inkpi/contracts.py`.

  跨进程和跨模块的公共行为使用 `inkpi/contracts.py` 中的类型化 contracts。

- Secrets live in `.env` or service environment config. They **never** go into `config.json`.

  Secrets 保存在 `.env` 或服务环境配置中，**永远不写入** `config.json`。

## Local Setup

InkPi requires Python 3.12 and uses `uv` as the sole package manager.

InkPi 需要 Python 3.12，使用 `uv` 作为唯一包管理器。

```bash
uv sync --extra dev
uv run pytest -q
uv run python -m compileall -q inkpi tests
uv run ruff check inkpi tests
```

!!! warning "Do Not Use pip"
    Never use `pip install`, `python -m venv`, or `virtualenv`. Always use `uv`.

    不要使用 `pip install`、`python -m venv` 或 `virtualenv`。始终使用 `uv`。

Don't install the `rpi` dependency group on non-Linux dev machines. On a Raspberry Pi:

不要在非 Linux 开发机上安装 `rpi` 依赖组。在 Raspberry Pi 上：

```bash
uv sync --extra rpi
```

## Preview Pages

Render pages in environments without display hardware:

在没有 display 硬件的环境中渲染页面：

```bash
# Mock data preview (no network or external services needed)
# Mock data preview (无需网络或外部服务)
uv run inkpi-preview overview --mock-data --output tmp/overview.png

# Live data preview (requires secrets in .env)
# Live data preview (需要 .env 中的 secrets)
uv run inkpi-preview overview --output tmp/overview-live.png
```

Every page must render an exact `800x480` grayscale image. When modifying a page, preview both the normal state and the failure state. Use `--mock-data` for fast UI layout iteration.

每个页面必须渲染精确的 `800x480` 灰度图像。修改页面时，同时预览正常状态和失败状态。使用 `--mock-data` 进行快速 UI 布局迭代。

### E-Ink Preview

Add `--eink-preview` to apply 4-level grayscale Floyd-Steinberg dithering, simulating the physical e-ink panel:

添加 `--eink-preview` 应用 4 级灰度 Floyd-Steinberg 抖动，模拟物理 e-ink 面板效果：

```bash
uv run inkpi-preview overview --mock-data --eink-preview --output tmp/overview-eink.png
```

!!! tip "Preview Output Path"
    Preview images generated for local simulation or tests should go into the project `tmp/` directory, not system `/tmp`.

    本地仿真和测试生成的 preview 图片应写入项目内 `tmp/` 目录，不要写入系统 `/tmp`。

## Run Services Locally

Use temporary sockets to avoid depending on the systemd-managed `/run/inkpi-display` and `/run/inkpi-core` directories:

使用临时 socket，避免依赖 systemd 管理的 `/run/inkpi-display` 和 `/run/inkpi-core` 目录：

```bash
# Terminal 1: Display service
uv run inkpi-display --socket /tmp/inkpi-display.sock
```

```bash
# Terminal 2: Core service
INKPI_REFRESH_SECONDS=10 uv run inkpi-core \
  --socket /tmp/inkpi-core.sock \
  --display-socket /tmp/inkpi-display.sock \
  --config /tmp/inkpi-config.json
```

```bash
# Terminal 3: Query and control (查询和控制)
uv run inkpi-ctl --socket /tmp/inkpi-core.sock status
uv run inkpi-ctl --socket /tmp/inkpi-core.sock pages
uv run inkpi-ctl --socket /tmp/inkpi-core.sock page codex_usage disable
```

### Admin Portal

```bash
uv run inkpi-admin \
  --host 127.0.0.1 \
  --port 8081 \
  --core-socket /tmp/inkpi-core.sock \
  --admin-token dev-local-token
```

Open `http://127.0.0.1:8081/` to see the portal, or hit `http://127.0.0.1:8081/api/status` for a JSON status dump.

打开 `http://127.0.0.1:8081/` 查看门户，或查询 `http://127.0.0.1:8081/api/status` 获取 JSON 状态。

Mutation routes require `X-InkPi-Admin-Token: <token>` or `Authorization: Bearer <token>`. Current network mutation endpoints only return in-memory queue operations and never call NetworkManager.

Mutation 路由需要 `X-InkPi-Admin-Token: <token>` 或 `Authorization: Bearer <token>`。当前网络 mutation 端点只返回内存队列操作，不会调用 NetworkManager。

Dashboard page enable/disable endpoints are live and delegate to the core contract:

Dashboard 页面启用/禁用端点是实时的，委托给 core contract：

```bash
curl -X POST \
  -H 'X-InkPi-Admin-Token: dev-local-token' \
  http://127.0.0.1:8081/api/dashboard/pages/codex_usage/disable
```

On machines without Waveshare hardware, the display adapter runs in simulation mode while keeping refresh policy behavior intact.

在没有 Waveshare 硬件的机器上，display adapter 运行在 simulation mode，同时保持 refresh policy 行为不变。

## Font Policy

All rendering fonts are bundled in `inkpi/fonts/` and loaded via `importlib.resources`.

所有渲染字体打包在 `inkpi/fonts/` 中，通过 `importlib.resources` 加载。

!!! danger "No System Font Fallbacks"
    System font paths (`/usr/share/fonts`, `/System/Library/Fonts`, etc.) are **forbidden** in source code. Architecture test `tests/test_font_architecture.py` enforces this policy.

    系统字体路径（`/usr/share/fonts`、`/System/Library/Fonts` 等）**禁止**出现在源代码中。架构测试 `tests/test_font_architecture.py` 强制执行此策略。

### Bundled Fonts

| File | Purpose |
|------|---------|
| `MapleMono-CN-Regular.ttf` | Regular text (常规文本) |
| `MapleMono-CN-Medium.ttf` | Medium weight (中等粗细) |
| `MapleMono-CN-SemiBold.ttf` | Semibold (半粗体) |
| `MapleMono-CN-Bold.ttf` | Bold (粗体) |
| `MapleMono.ttf` | English fallback |
| `NotoEmoji-Regular.ttf` | Emoji |

### Adding a New Font

1. Drop the TTF file into `inkpi/fonts/`.

   将 TTF 文件放入 `inkpi/fonts/`。

2. Register it in the `_load_font()` weight candidate list in `inkpi/ui/drawing.py`.

   在 `inkpi/ui/drawing.py` 的 `_load_font()` 权重候选列表中注册。

3. Update architecture tests if needed.

   更新架构测试（如有需要）。

## Add A Dashboard Page

1. Implement the `DashboardPage` protocol under `inkpi/dashboard/pages/`.

   在 `inkpi/dashboard/pages/` 下实现 `DashboardPage` 协议。

2. Give the page a stable `page_id` and a readable `name`.

   给页面一个稳定的 `page_id` 和可读的 `name`。

3. Keep collection and rendering logic independent of display hardware.

   保持采集和渲染逻辑独立于 display 硬件。

4. Inject management facts or other data providers through contracts.

   通过 contracts 注入 management facts 或其他 data provider。

5. Register the page explicitly in the core composition root.

   在 core composition root 中显式注册页面。

6. Add the page to the example config at `config/inkpi.example.json`.

   将页面添加到示例配置 `config/inkpi.example.json`。

7. Add tests for render size, failure, configuration, and rotation.

   添加 render size、failure、configuration 和 rotation 测试。

8. Generate and inspect the preview.

   生成并检查 preview。

Pages should degrade to a renderable failure state whenever possible. Unhandled page failures are isolated by core, logged into status, and skipped on the next scheduling cycle.

页面应在可能的情况下降级为可渲染的失败状态。未处理的页面失败会被 core 隔离、记录到状态中，并在下次调度时跳过。

## Change Display Behavior

Display policy changes **belong only** in `inkpi/display/`.

Display 策略变更**只属于** `inkpi/display/`。

Invariants that must hold:

必须保持的不变量：

- Complete frame input (完整帧输入)
- Serialized hardware access (序列化硬件访问)
- Stale normal pending frames can be replaced by new frames (过时的 normal pending frame 可以被新帧替换)
- Immediate frames cannot be replaced by normal frames (immediate frame 不能被 normal frame 替换)
- Page switches and recovery use full refresh (页面切换和恢复使用 full refresh)
- Failed refreshes invalidate frame history (失败的刷新使帧历史失效)
- Default longevity policy forces full refresh after 50 partials (默认 longevity 策略在 50 次 partial 后强制 full refresh)
- Panel enters sleep on service shutdown (服务关闭时面板进入 sleep)

Use a fake backend to write focused engine tests before hardware validation.

在硬件验证之前，使用 fake backend 编写聚焦的 engine 测试。

## Configuration And Contracts

`inkpi-core` loads and atomically writes versioned JSON config. Any new editable field needs:

`inkpi-core` 加载并原子写入版本化 JSON 配置。任何新的可编辑字段必须有：

- A typed config field (类型化的配置字段)
- Validation and safe defaults (校验和安全默认值)
- Backward-compatible parsing for the current schema version, or an intentional schema version migration (当前 schema version 的向后兼容解析，或有意的 schema version 迁移)
- Tests for valid and invalid values (有效和无效值的测试)
- Documentation in `config/inkpi.example.json`

Contract changes must preserve the `CONTRACT_VERSION` protocol, or intentionally bump it when server and client change together.

Contract 变更必须保持 `CONTRACT_VERSION` 协议，或在有匹配的 server/client 变更时有意递增它。

## Quality Gates

Must pass before deployment:

部署前必须通过：

```bash
uv sync --extra dev
uv run pytest -q
uv run python -m compileall -q inkpi tests
uv run ruff check inkpi tests
git diff --check
uv build
```

For display or orchestration changes, also run the local dual-service smoke test and check previews for both pages.

对于 display 或编排变更，还需运行本地双服务 smoke test 并检查两个页面的 preview。

## Raspberry Pi Deployment

The deploy target is reachable via `ssh meta_pi`. The expected checkout path is `/home/meta/Workspace/InkPi`.

部署目标通过 `ssh meta_pi` 访问。预期 checkout 路径为 `/home/meta/Workspace/InkPi`。

See the [Deployment Guide](deployment.md) for detailed steps.

详细部署步骤参见 [Deployment Guide](deployment.md)。

## Future Management Work

The portal should run independently of display refresh work. It consumes a typed core client and delegates privileged NetworkManager changes to a narrow-scope helper. Don't put arbitrary shell execution or privileged network operations inside dashboard pages, core request handlers, or the portal process.

门户应独立于 display 刷新工作运行。它消费类型化的 core client，并将特权 NetworkManager 变更委托给窄 scope helper。不要在 dashboard 页面、core 请求处理器或门户进程中放置任意 shell 执行或特权网络操作。

The current admin design goals live in [Admin Portal Design](../services/admin-portal-design.md). Keep portal layout, network workflows, and service boundaries aligned with that document. The network access policy is intentionally a pure function and testable. Extend `inkpi/admin/network_policy.py` rather than embedding hotspot or Wi-Fi decisions into HTTP handlers or helper implementations.

当前 admin 设计目标在 [Admin Portal Design](../services/admin-portal-design.md) 中。保持门户布局、网络工作流和服务边界与该文档一致。网络访问策略有意设计为纯函数且可测试；扩展 `inkpi/admin/network_policy.py` 而不是将 hotspot 或 Wi-Fi 决策嵌入 HTTP handler 或 helper 实现。

Network operations use `inkpi/admin/operations.py` as the allowlist helper contract. Don't add admin routes that forward arbitrary shell commands or store secret request fields in the operation history.

网络操作使用 `inkpi/admin/operations.py` 作为允许列表 helper 合约。不要添加转发任意 shell 命令或在操作历史中存储 secret 请求字段的 admin 路由。

Dry-run helper plans live in `inkpi/admin/network_helper.py`. Treat those plans as auditable command vectors for a future privileged executor, not as permission to run commands from the admin process. Any real executor must keep secrets out of argv, JSON payloads, events, and logs.

Dry-run helper 规划在 `inkpi/admin/network_helper.py` 中。将这些计划视为未来特权执行器的可审查命令向量，而不是从 admin 进程运行命令的许可。任何真实执行器都必须将 secrets 从 argv、JSON payload、事件和日志中排除。

Mutation auth uses `inkpi/admin/auth.py`. Keep read-only local state available for recovery, but require a configured token and reject cross-origin browser requests before queuing any mutation.

Mutation 认证使用 `inkpi/admin/auth.py`。保持只读本地状态可用于恢复，但在排队任何 mutation 之前要求配置 token 并拒绝跨域浏览器请求。

Admin-visible events use `inkpi/admin/events.py`. Keep the stream bounded and sanitized. Don't expose raw journal output or unfiltered request payloads through `/api/events`.

Admin 可见事件使用 `inkpi/admin/events.py`。保持流有界且脱敏；不要通过 `/api/events` 暴露原始 journal 输出或未过滤的请求 payload。
