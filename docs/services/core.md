# inkpi-core Service

`inkpi-core` 是 InkPi 的中枢编排服务（orchestration hub），负责页面调度、配置持久化、
数据收集编排，并向其他服务暴露统一的 Control API。

## Service Role

| 职责 | 说明 |
|------|------|
| 编排 | 驱动 dashboard 页面的 collect → render → submit 循环 |
| 配置 | 加载、校验、原子写入版本化 JSON 配置 |
| 调度 | 通过 `DataScheduler` 管理各数据源的采集频率 |
| 控制 | 通过 Unix socket 提供 Control API，供 `inkpi-ctl` 和 `inkpi-admin` 调用 |

!!! warning "Ownership Boundary"
    `inkpi-core` 不拥有 SPI/GPIO，不决定刷新模式，不直接渲染像素。
    这些职责分别属于 `inkpi-display` 和 dashboard 页面。

## Lifecycle

`start()` 启动 `DataScheduler` 和 worker 线程，进入页面轮转循环。
`stop()` 停止调度器和 worker。`build_core()` 是 production composition root。
详见源码 `inkpi/core/service.py`。

## Control API

通过 Unix socket 暴露 JSON-RPC 风格的 Control API（`action` + `payload` → JSON 响应）。

| Action | 说明 | 返回类型 |
|--------|------|---------|
| `health` | 服务健康检查 | `{healthy, last_error}` |
| `get_pages` | 列出所有页面及其状态 | `{pages: [PageStatus]}` |
| `set_page_enabled` | 启用/禁用指定页面 | `DashboardConfigResult` |
| `get_dashboard_status` | Dashboard 调度器状态 | `DashboardStatus` |
| `get_display_status` | 代理查询 display 状态 | `DisplayStatus` |
| `get_system_status` | 系统 facts | `SystemStatus` |
| `get_network_status` | 网络 facts | `NetworkStatus` |
| `get_core_status` | Core 自身状态 | `{healthy, last_error, last_display_result}` |

`set_page_enabled` 会拒绝禁用最后一个 enabled 页面（`error_code="last_enabled_page"`）。

```bash
uv run inkpi-ctl --socket /tmp/inkpi-core.sock pages
uv run inkpi-ctl --socket /tmp/inkpi-core.sock page codex_usage disable
```

## Configuration

配置文件位于 `~/.config/inkpi/config.json`（`INKPI_CONFIG` 环境变量可覆盖）。

```json
{
  "schema_version": 1,
  "dashboard": {"rotation_interval_seconds": 300, "pages": [{"id": "overview", "enabled": true}]},
  "display": {"policy": "longevity", "max_partial_refreshes": 50, "meaningful_change_ratio": 0.0005,
    "partial_change_ratio": 0.12, "region_repair_threshold": 30, "region_padding": 8,
    "orientation": "landscape"}
}
```

### DisplayConfig Thresholds

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_partial_refreshes` | 50 | 连续 partial 上限，达到后强制 full |
| `meaningful_change_ratio` | 0.0005 | 低于此比例视为无变化，skip |
| `partial_change_ratio` | 0.12 | 高于此比例视为大变化，full |
| `region_repair_threshold` | 30 | 同区域 partial 次数达到后触发 repair |
| `region_padding` | 8 | dirty region 外扩像素 |
| `orientation` | `landscape` | 屏幕方向 |

Secrets 通过 `.env` 或环境变量注入，**永不写入 config.json**。
支持：`EINK_GITHUB_API_KEY` / `EINK_GITHUB_TOKEN`、`EINK_WEATHER_API_KEY`。

## Run Locally

```bash
INKPI_DISPLAY_SOCKET=/tmp/inkpi-display.sock uv run inkpi-display
INKPI_DISPLAY_SOCKET=/tmp/inkpi-display.sock \
  INKPI_CORE_SOCKET=/tmp/inkpi-core.sock uv run inkpi-core
uv run inkpi-ctl --socket /tmp/inkpi-core.sock status
```

!!! tip "Config Override"
    使用 `--config /tmp/inkpi-config.json` 指定临时配置文件。
