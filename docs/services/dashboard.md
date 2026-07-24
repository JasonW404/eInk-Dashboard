# Dashboard Pages and Rendering

Dashboard 是 InkPi 的页面系统。每个页面实现统一协议，负责数据采集和帧渲染，
产出 800x480 灰度图像。页面不接触 display driver，不选择刷新模式。

## DashboardPage Protocol

```python
class DashboardPage(Protocol):
    page_id: str
    name: str
    def collect(self) -> Any: ...
    def render(self, snapshot: Any) -> Image.Image: ...
```

| 方法 | 职责 |
|------|------|
| `collect()` | 采集数据，返回类型化快照 |
| `render(snapshot)` | 渲染为 800x480 `mode="L"` PIL Image |

!!! danger "Rendering Constraints"
    输出必须 `800x480`、`mode="L"`。**禁止**导入 display driver 或 `inkpi.display` 下任何模块。

## Layout

```
┌──────────────────────────────────────────────┐
│ Date / Weather / Version          (y=8, h=41)│
├──────────────────────────────────────────────┤
│ GitHub Panel                      (y=59,h=176)│
├──────────────────────────────────────────────┤
│ Codex Panel                      (y=248,h=118)│
├───────────────────────┬──────────────────────┤
│ System Pressure       │ Network   (y=379,h=96)│
└───────────────────────┴──────────────────────┘
     800 x 480 (landscape)
```

内置面板：GitHubPanel（用户指标 + 热力图）、CodexPanel（订阅用量）、
System Pressure（CPU/RAM/LOAD）、Network（连接 + IP）。详见 `inkpi/dashboard/rendering/`。

## Font System

所有字体打包在 `inkpi/fonts/`，通过 `importlib.resources` 加载。**禁止**系统字体路径。
架构测试 `tests/test_font_architecture.py` 强制执行。

### Bundled Fonts

| 文件 | 用途 |
|------|------|
| `MapleMono-CN-Regular.ttf` | 常规文本 |
| `MapleMono-CN-Medium.ttf` | 中等粗细 |
| `MapleMono-CN-SemiBold.ttf` | 半粗体 |
| `MapleMono-CN-Bold.ttf` | 粗体 |
| `MapleMono.ttf` | 英文 fallback |
| `NotoEmoji-Regular.ttf` | Emoji 支持 |

### Weight System

`FontWeight = Literal["regular", "medium", "semibold", "bold"]`。
`_load_font()` 按权重选择候选字体并依次 fallback，例如 `semibold`：
CN-SemiBold → CN-Medium → CN-Regular → MapleMono。

```python
@lru_cache(maxsize=64)
def _load_font(font_size: int, font_weight: FontWeight = "regular") -> ImageFont.ImageFont: ...
@lru_cache(maxsize=16)
def _load_icon_font(font_size: int) -> ImageFont.ImageFont: ...
```

## Preview Commands

```bash
uv run inkpi-preview overview --mock-data --output tmp/overview.png
uv run inkpi-preview overview --output tmp/overview-live.png
uv run inkpi-preview overview --mock-data --eink-preview --output tmp/overview-eink.png
```

Preview 图片应写入项目内 `tmp/` 目录，不要写入系统 `/tmp`。

## Adding a New Page

1. 在 `inkpi/dashboard/pages/` 下创建页面模块。
2. 实现 `DashboardPage` 协议（`page_id`, `name`, `collect()`, `render()`）。
3. 在 `build_core()` 中注册：`DashboardController([OverviewPage(mgmt), MyPage()], config, ...)`。
4. 在 `config/inkpi.example.json` 的 `dashboard.pages` 中添加条目。
5. 添加测试：render size、failure handling、configuration、rotation。
6. 生成 preview 验证布局。

## Grayscale Palette

4 级灰度定义在 `inkpi/ui/constants.py`：

| 常量 | 值 | 用途 |
|------|-----|------|
| `GRAY_WHITE` | 255 | 白色背景 |
| `GRAY_LIGHT` | 140 | 浅灰（次要文本） |
| `GRAY_MID` | 60 | 中灰（分隔线、标签） |
| `GRAY_BLACK` | 0 | 黑色（主要文本） |
