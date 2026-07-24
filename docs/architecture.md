# Architecture

> This document describes the multi-process architecture of InkPi.
> For development workflow, see the [Developer Guide](guides/developer-guide.md).

> 本文档描述 InkPi 的多进程架构设计。
> 开发规范见 [Developer Guide](guides/developer-guide.md)。

---

## Ownership Model

InkPi uses a strict-ownership multi-process architecture. Each module has a clearly defined responsibility boundary, and cross-module communication happens only through versioned contracts.

InkPi 采用严格模块所有权的多进程混合架构。每个模块有明确的职责边界，跨模块通信仅通过版本化契约完成。

```
┌─────────────────────────────────────────────────────────┐
│                    inkpi-core                           │
│  Orchestration · Config · Page Rotation · Coordination  │
│  编排调度 · 配置管理 · 页面轮转 · 服务协调              │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  dashboard   │  │  management  │  │   contracts   │  │
│  │  Pages+Data  │  │  Sys/Net     │  │  Versioned    │  │
│  │  页面与数据  │  │  系统/网络   │  │  DTO 版本化   │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
└──────────┬──────────────────┬───────────────────────────┘
           │ Unix socket      │ Unix socket
           ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│  inkpi-display   │  │   inkpi-admin    │
│  SPI/GPIO sole   │  │  Web portal :8081│
│  owner 独占      │  │  Status API +    │
│  Refresh policy  │  │  Control 控制    │
│  刷新策略决策    │  │  Auth + CORS     │
│  Panel lifecycle │  │  认证 + CORS     │
│  面板生命周期    │  │                  │
└──────────────────┘  └──────────────────┘
```

### Module Boundaries

| Module | Ownership | Forbidden |
|--------|-----------|-----------|
| `inkpi-core` | Scheduling, config, page rotation, service orchestration (调度、配置、页面轮转、服务编排) | Must not touch SPI/GPIO |
| `inkpi-display` | SPI/GPIO, panel lifecycle, all refresh decisions (SPI/GPIO、面板生命周期、全部刷新决策) | Must not care about data sources |
| `dashboard` | Page rendering, data aggregation (页面渲染、数据聚合) | Must not import display drivers |
| `management` | System/network facts (系统/网络事实) | Must not control dashboard state |
| `inkpi-admin` | Web portal, status API (Web 门户、状态 API) | Must not execute privileged network ops |
| `contracts` | Versioned immutable DTOs (版本化不可变 DTO) | Must not contain business logic |

!!! warning
    Dashboard pages submit complete grayscale frames. They cannot select a refresh mode or import the Waveshare driver. Code that violates this boundary is rejected by architecture tests.

    Dashboard 页面提交完整灰度帧。它们不能选择刷新模式，也不能 import Waveshare 驱动。违反此边界的代码会被架构测试拒绝。

---

## Data Flow

The full data flow, from collection to physical panel refresh, passes through five stages:

整个数据流从采集到物理面板刷新，经过五个阶段：

```
 ① Core requests render (Core 请求渲染)
        │
        ▼
 ② Page collects data ──→ contracts ──→ management
    (Page 采集数据)
        │
        ▼
 ③ Page returns 800x480 grayscale image + metadata
    (Page 返回 800x480 灰度图像 + 元数据)
        │
        ▼
 ④ Core submits complete frame to inkpi-display (Unix socket)
    (Core 提交完整帧到 inkpi-display)
        │
        ▼
 ⑤ Display serializes request → replaces stale normal frames
    → picks refresh action → drives panel → returns telemetry
    (Display 序列化请求 → 替换过期 normal 帧 → 选择刷新动作 → 驱动面板 → 返回遥测)
```

### Detailed Steps

1. **Core requests render**: core asks the dashboard controller for a render of the currently active page.

   Core 向 dashboard controller 请求当前活跃页面的渲染。

2. **Data collection**: the page gathers data through services or management contracts. Each provider can degrade independently. No single unavailable source blocks rendering.

   Page 通过 service 或 management 契约收集数据。每个 provider 可独立降级，任一数据源不可用不会阻塞渲染。

3. **Frame generation**: the page returns an 800x480 grayscale PIL Image along with page metadata (page_id, whether grayscale changes are present, etc.).

   Page 返回一张 800x480 灰度 PIL Image 和页面元数据（page_id、是否包含灰度变化等）。

4. **Frame submission**: core sends the complete frame and metadata to inkpi-display over a Unix socket. The payload is PNG-encoded frame data.

   Core 将完整帧和元数据通过 Unix socket 发送给 inkpi-display。传输的是 PNG 编码的帧数据。

5. **Refresh execution**: display enqueues the request into a serialized queue, replaces stale normal frames, picks a refresh action based on the longevity policy, drives the physical panel, and returns structured telemetry.

   Display 将请求排入序列化队列，替换过期的 normal 帧，根据 longevity policy 选择刷新动作，驱动物理面板，并返回结构化遥测数据。

!!! note
    Core also exposes page control and status query interfaces to the admin portal. Slow data collection and rendering never block control or status requests.

    Core 同时向 admin 门户暴露页面控制和状态查询接口。慢速的数据采集和渲染不会阻塞控制/状态请求。

---

## Display Strategy

The Waveshare 4.26-inch driver sends the full buffer even during a partial refresh. Dirty-region analysis is therefore an input to the refresh decision, not a rectangular transfer mechanism.

Waveshare 4.26 英寸驱动即使执行 partial refresh 也发送完整缓冲区。因此脏区分析是刷新决策的输入，而非矩形传输机制。

### Refresh Policy (Longevity-First)

The refresh policy prioritizes panel lifespan. Decisions follow this priority order:

刷新策略以面板寿命为优先，按以下优先级决策：

| Condition | Action | Reason |
|-----------|--------|--------|
| Startup / Recovery | **Full** | Ensure panel state consistency (确保面板状态一致) |
| Page switch | **Full** | Major content change (内容大幅变化) |
| Grayscale change | **Full** | Partial cannot handle grayscale transitions (partial 不支持灰度切换) |
| Large-area change | **Full** | Exceeds reasonable partial range (超出 partial 合理范围) |
| No visual change | **Skip** | Avoid meaningless refresh (避免无意义刷新) |
| Consecutive partial limit reached | **Full** | Force full after default 5 partials (默认 5 次后强制全刷) |
| Region repair triggered | **Repair** | Clear ghosting (清除残影) |
| Everything else | **Partial** | Small monochrome same-page changes (小范围单色同页变化) |

### Dirty-Region Analysis

Dirty-region detection uses `ImageChops` to compare the current frame against the previous one:

脏区检测使用 `ImageChops` 对比当前帧与上一帧的差异：

1. Compute the bounding box of changed pixels (计算变化像素的边界框)
2. Align to 8-pixel boundaries, a hardware requirement (对齐到 8 像素边界)
3. Add region padding (添加 region padding)
4. Feed the result as input to the refresh decision (将结果作为刷新决策的输入参数)

### Region Tracking

`_RegionTracker` tracks partial refresh counts per region:

`_RegionTracker` 按区域追踪 partial 刷新次数：

- Each region maintains an independent partial counter (每个区域维护独立的 partial 计数器)
- When the repair threshold is reached, a region repair fires (a white-baseline mini full refresh) (达到修复阈值时触发 region repair)
- All region counters reset after a full refresh completes (全刷完成后重置所有区域计数器)
- Default max partial streak is 5, configurable (默认最大 partial 连续次数为 5，可配置)

### Frame Queue

Display uses a serialized single-thread worker to process frame requests:

Display 使用序列化单线程 worker 处理帧请求：

- Queue maxsize=1, preventing stale frame buildup (队列 maxsize=1，保证不积压过期帧)
- **Normal frames** can be replaced by later frames, called coalescing (**normal 帧**可被后续帧替换)
- **Immediate frames** cannot be replaced, used for recovery/shutdown and other critical ops (**immediate 帧**不可被替换，用于恢复/关机等关键操作)
- After a failure, a full recovery refresh fires automatically (失败后自动触发 full recovery refresh)

!!! warning
    Automatic deep sleep between refreshes is deferred until validated on the physical HAT. Currently the panel only enters sleep during service shutdown.

    自动深度睡眠（两次刷新之间）已推迟到物理 HAT 验证后再启用。当前仅在服务关闭时让面板进入睡眠。

---

## Configuration and Contracts

### Configuration

Core owns a versioned JSON config file. Writes are atomic:

Core 拥有版本化 JSON 配置文件，写入采用原子操作：

- Config path: `~/.config/inkpi/config.json` (配置路径)
- Example config: `config/inkpi.example.json` (示例配置)
- Write strategy: write to a temp file first, then atomic rename (先写临时文件，再原子 rename)
- Page control is validated and idempotent. Disabling the last enabled page is rejected (页面控制经过验证且幂等，禁用最后一个启用页面会被拒绝)

!!! note
    Secrets (API keys, tokens, etc.) are supplied through `.env` files and never enter JSON config, logs, tests, or docs.

    密钥（API key、token 等）通过 `.env` 文件提供，不进入 JSON 配置、日志、测试或文档。

### Local Controls

Core exposes the following local control interfaces:

Core 暴露以下本地控制接口：

| Control | Description |
|---------|-------------|
| `get_pages` | Get all pages and their enabled status (获取所有页面及其启用状态) |
| `set_page_enabled` | Enable or disable a specific page (启用或禁用指定页面) |
| `get_dashboard_status` | Get dashboard runtime status (获取 dashboard 运行状态) |
| `get_display_status` | Get display engine telemetry (获取显示引擎遥测数据) |
| `get_system_status` | Get system resource snapshot (获取系统资源快照) |
| `get_network_status` | Get network status snapshot (获取网络状态快照) |

### Contracts

Cross-process and cross-module behavior uses typed DTOs from `inkpi/contracts.py`:

跨进程和跨模块行为使用 `inkpi/contracts.py` 中的类型化 DTO：

- All contracts carry a `CONTRACT_VERSION` field (所有契约携带 `CONTRACT_VERSION` 字段)
- DTOs are immutable, implemented as frozen dataclasses (DTO 不可变，frozen dataclass)
- Requests and responses are JSON-serializable (请求和响应均为 JSON 可序列化)
- Dashboard and management share data or control only through contracts (Dashboard 和 management 仅通过契约共享数据或控制)

---

## IPC Transport

Services communicate using versioned JSON over Unix socket:

服务间通信使用版本化 JSON over Unix socket：

```
Client                          Server
  │                               │
  │── JSON request ──────────────▶│
  │   (method, params, version)   │
  │                               │
  │◀── JSON response ─────────────│
  │   (result/error, version)     │
  │                               │
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| Unix socket (not TCP) | Local-only communication, no network exposure needed (本地通信，无需网络暴露) |
| JSON (not protobuf) | Readable, easy to debug, sufficient performance (可读性好，调试方便，性能足够) |
| Versioned contracts | Forward-compatible, services can upgrade independently (支持向前兼容，服务可独立升级) |
| PNG frame transfer | Complete frames as payload, no raw pixel transfer (完整帧作为 payload，不传输原始像素) |
| Non-blocking control | Slow rendering never blocks status/control requests (慢速渲染不阻塞状态/控制请求) |

### Socket Paths

| Service | systemd Default | Local Dev |
|---------|-----------------|-----------|
| inkpi-display | `/run/inkpi/display.sock` | `$INKPI_DISPLAY_SOCKET` |
| inkpi-core | `/run/inkpi/core.sock` | `$INKPI_CORE_SOCKET` |

---

## Font Policy

All rendering fonts are bundled in `inkpi/fonts/` and loaded via `importlib.resources`. System font paths are forbidden.

所有渲染字体内置于 `inkpi/fonts/` 目录，通过 `importlib.resources` 加载。禁止使用系统字体路径。

### Bundled Fonts

| File | Size | Purpose | License |
|------|------|---------|---------|
| `MapleMono-CN-Regular.ttf` | 18 MB | Body text regular, includes CJK (正文 regular，含 CJK) | SIL OFL 1.1 |
| `MapleMono-CN-Medium.ttf` | 18 MB | Body text medium (正文 medium) | SIL OFL 1.1 |
| `MapleMono-CN-SemiBold.ttf` | 18 MB | Body text semibold (正文 semibold) | SIL OFL 1.1 |
| `MapleMono-CN-Bold.ttf` | 18 MB | Body text bold (正文 bold) | SIL OFL 1.1 |
| `MapleMono.ttf` | 259 KB | Latin-only fallback (Latin-only 回退) | SIL OFL 1.1 |
| `NotoEmoji-Regular.ttf` | ~890 KB | Unicode emoji | SIL OFL 1.1 |

### Enforcement

The font policy is enforced by architecture tests:

字体策略由架构测试强制执行：

- `tests/test_font_architecture.py` (10 tests) scans all source code (`tests/test_font_architecture.py`，10 个测试，扫描所有源码)
- System paths like `/usr/share/fonts` and `/System/Library/Fonts` are forbidden (禁止出现系统路径)
- All bundled fonts must exist and be loadable (验证所有 bundled 字体存在且可加载)
- Font loading goes through `_load_font()` and `_load_emoji_font()` in `inkpi/ui/drawing.py` (字体加载统一通过 `drawing.py`)

!!! warning
    New font requirements must bundle the TTF in `inkpi/fonts/` and register it in `drawing.py`. Adding system font fallback paths is not allowed.

    新增字体需求必须将 TTF 文件放入 `inkpi/fonts/` 并在 `drawing.py` 中注册。不允许添加系统字体回退路径。
