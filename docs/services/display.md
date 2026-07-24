# inkpi-display Service

`inkpi-display` 是 InkPi 中唯一拥有 SPI/GPIO 访问权限的服务。
它独占物理面板的生命周期管理，并做出所有刷新决策（full / partial / skip / region repair）。

!!! danger "Sole Hardware Owner"
    只有 `inkpi-display` 可以初始化 EPD、发送帧数据、选择刷新模式。
    Dashboard 页面和其他服务**禁止**导入 display driver 或请求特定刷新模式。

## Service Architecture

```
inkpi-core ──(Unix socket)──> inkpi-display
                                  │
                                  ├── DisplayEngine (worker thread)
                                  │     ├── _decide()  → refresh policy
                                  │     └── _process() → execute refresh
                                  │
                                  └── WaveshareBackend
                                        └── EPDAdapter (hardware / simulation)
```

`inkpi-core` 通过 `DisplayClient` 提交完整帧。`DisplayEngine` 在 worker 线程中
序列化所有帧提交，应用以面板寿命为优先的刷新策略。

## Refresh Policy

`_decide()` 是刷新策略的核心决策函数，返回 `(action, reason, region)` 三元组。

### Decision Table

| 条件 | Action | Reason |
|------|--------|--------|
| 无前帧（启动/恢复） | `full` | `startup_or_recovery` |
| 页面切换 | `full` | `page_changed` |
| 无有意义的像素变化 | `skipped` | `no_meaningful_visual_change` |
| 灰度变化（单色相同但灰度不同） | `full` | `grayscale_change` |
| 变化比例超过 `partial_change_ratio` | `full` | `large_visual_change` |
| 连续 partial 达到 `max_partial_refreshes` | `full` | `partial_refresh_limit` |
| 同区域 partial 达到 `region_repair_threshold` | `region_repair` | `region_repair_threshold` |
| 默认（小范围单色同页变化） | `partial` | `small_monochrome_same_page_change` |

### Action Types

| Action | 说明 | 硬件操作 |
|--------|------|---------|
| `full` | 全屏 4-gray 刷新 | `backend.display(image, "full")` |
| `partial` | 区域局部刷新 | `backend.display_region(image, region)` |
| `region_repair` | 区域修复刷新（无 old buffer） | `backend.repair_region(image, region)` |
| `skipped` | 无有意义的变化，跳过 | 无 |

## Simulation Mode

当 `inkpi.lib.waveshare_epd.epd4in26` 导入失败时（例如 macOS 开发环境），
`EPDAdapter` 自动进入 simulation mode。所有操作记录日志但不执行硬件命令，
返回值与真实硬件一致。这使得刷新策略可以在无硬件环境中完整测试。

## FileBackend

`FileBackend` 将每一帧写入磁盘作为 PNG，用于离线检查刷新决策。
文件命名格式：`frame_0001_full.png`、`frame_0002_partial_region_0_48_800_120.png`。

!!! tip "Testing with FileBackend"
    在测试中使用 `FileBackend` 替代 `WaveshareBackend`，
    可以检查 Engine 的刷新决策是否正确，无需真实硬件。

## Run Locally

```bash
# 使用临时 socket
INKPI_DISPLAY_SOCKET=/tmp/inkpi-display.sock uv run inkpi-display

# 指定配置文件
INKPI_DISPLAY_SOCKET=/tmp/inkpi-display.sock \
INKPI_CONFIG=/tmp/inkpi-config.json \
uv run inkpi-display
```

在无 Waveshare 硬件的机器上，adapter 自动进入 simulation mode，
刷新策略行为保持不变。
