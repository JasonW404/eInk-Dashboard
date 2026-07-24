# UI Rendering Module

本模块实现 800x480 横屏 4 灰度墨水屏渲染。

## Architecture

```
src/ui/
├── __init__.py          # 包导出
├── constants.py         # 屏幕尺寸与灰度常量
├── drawing.py           # 绘图工具函数
├── renderer.py          # 主渲染器（组合所有面板）
├── codex_panel.py       # Codex 用量面板
└── github_panel.py      # GitHub 统计面板
```

## Layout

```
┌──────────────────────────────────────────────┐
│ Date / Time / Weather / Version              │
├──────────────────────────────────────────────┤
│ GitHub User Metrics       Contribution Month │
├──────────────────────────────────────────────┤
│ Codex Usage: 5-hour window | Weekly window   │
├───────────────────────┬──────────────────────┤
│ System                │ Network              │
└───────────────────────┴──────────────────────┘
     800 x 480 (landscape)
```

The GitHub panel shows only four numeric metrics: configured user commits,
configured user code line changes, that user's commits in the configured
organization, and that user's organization-scoped code line changes.
Dynamic values use fixed-width fields and stable coordinates so refreshes do
not shift neighboring content.

## Usage

### Generate Preview

```bash
uv run inkpi-preview overview --mock-data --output tmp/overview.png
uv run inkpi-preview overview --output tmp/overview-live.png
```

这会生成 PNG 预览文件用于验证布局和灰度效果。
本地仿真和测试生成的 preview 图片应写入项目内 `tmp/` 目录。

### In Application

`DashboardRenderer` 已集成到 `inkpi-core` 服务中。每个刷新周期会：

1. 调用 `DashboardDataService.collect()` 获取数据快照
2. 调用 `DashboardRenderer.render(snapshot)` 生成图像
3. 将图像发送到 `inkpi-display` 服务进行屏幕刷新

## Grayscale Palette

4 灰度级别定义在 `constants.py`：

- `GRAY_WHITE = 255` （白色背景）
- `GRAY_LIGHT = 140` （浅灰）
- `GRAY_MID = 60` （中灰）
- `GRAY_BLACK = 0` （黑色文字）

## Panel Customization

每个面板继承相同模式：

```python
class MyPanel:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def render(self, data: MyData) -> Image.Image:
        image = Image.new("L", (self._width, self._height), GRAY_WHITE)
        # ... drawing logic ...
        return image
```

修改布局时，调整 `renderer.py` 中的尺寸常量和 paste 坐标即可。
