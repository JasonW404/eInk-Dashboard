# Phase 5: Font Bundling

> **Status:** ✅ Done
> **Back to:** [Development Plan](../plan.md)

---

## Problem Statement

Before Phase 5, font management had several issues:

Phase 5 开始前，字体管理存在多个问题:

| Problem | Description |
|---------|-------------|
| Duplicate implementations | 6 `_load_font()` scattered across panel files, nearly identical logic |
| System font fallback | Multiple code paths included `/usr/share/fonts/`, depending on system-installed fonts |
| Symbola not bundled | Emoji font relied on system install, often missing on Pi |
| Fonts outside package | `assets/fonts/` lived at project root, not inside the Python package |
| CWD-relative paths | Some code loaded fonts via relative paths, depending on current working directory |

These problems caused:

- Rendering inconsistency between macOS dev machines and Pi deployment
- Copy-paste font loading code for every new panel
- System font updates could cause unexpected rendering changes

---

## Font Selection

### Retained: MapleMono-CN

MapleMono-CN is the existing primary text font, covering CJK and Latin
characters. It provides 4 weights (Regular / Medium / SemiBold / Bold),
meeting all text rendering needs.

MapleMono-CN 是项目已有的主力文本字体，覆盖 CJK 和 Latin 字符。
提供 4 个字重 (Regular / Medium / SemiBold / Bold)，满足全部文本渲染需求。

**Why retained:** Already validated in production, complete CJK coverage,
stable rendering quality.

### Added: Symbols Nerd Font Mono

Used for weather icons, status indicators, developer tool symbols, and
similar scenarios.

用于天气图标、状态指示器、开发者工具符号等场景。

**Why chosen:**

- Covers 3000+ icon glyphs (weather, Git, GitHub, system monitoring, etc.)
- Mono variant ensures monospace alignment
- MIT license, commercially friendly

### Added: Noto Emoji

Used for Unicode emoji character rendering.

用于 Unicode emoji 字符渲染。

!!! warning "Key Finding: Nerd Fonts Do Not Include Emoji"
    During research we discovered the Nerd Fonts family **does not** include
    the Unicode emoji block. Nerd Fonts focuses on developer tool icons and
    powerline symbols. Emoji rendering requires a separate font.
    Noto Emoji was added to fill this gap.

    调研过程中发现 Nerd Fonts 系列 **不包含** Unicode emoji 区块。
    Nerd Fonts 专注于 developer tool 图标和 powerline 符号，
    emoji 渲染需要单独的字体。因此引入 Noto Emoji 作为补充。

---

## Implementation

### Font Directory Migration

```
# Before
assets/fonts/          (project root, outside package)

# After
inkpi/fonts/           (inside Python package, distributed with pip install)
```

### Unified Loading Entry Point

Removed 5 duplicate `_load_font()` implementations. Only the version in
`inkpi/ui/drawing.py` remains:

删除 5 个重复的 `_load_font()` 实现，仅保留 `inkpi/ui/drawing.py` 中的版本:

```python
from importlib.resources import files

_FONT_DIR = files("inkpi").joinpath("fonts")

@lru_cache(maxsize=64)
def _load_font(font_size: int, font_weight: FontWeight = "regular"):
    # Look up candidate font files by weight, fall back to MapleMono.ttf
    ...

@lru_cache(maxsize=16)
def _load_icon_font(font_size: int):
    # Load SymbolsNerdFontMono, fall back to _load_font on failure
    ...
```

### Eliminate System Fallback

Global search and removal of all system font path references:

全局搜索并删除所有系统字体路径引用:

- `/usr/share/fonts/` (Linux)
- `/System/Library/Fonts/` (macOS)
- `/Library/Fonts/` (macOS)
- `C:\Windows\Fonts\` (Windows)

The final fallback strategy: bundled font chain fallback, then
`ImageFont.load_default()` as the last resort.

### importlib.resources

Uses `files("inkpi").joinpath("fonts")` to resolve font paths. No longer
depends on current working directory or hardcoded paths. This ensures:

使用 `files("inkpi").joinpath("fonts")` 解析字体路径，
不再依赖当前工作目录或硬编码路径。这确保:

- Fonts distribute with the package after `pip install`
- Fonts load correctly from any working directory
- Supports zipimport and other packaging scenarios

### pyproject.toml Configuration

```toml
[tool.setuptools.package-data]
inkpi = ["fonts/*.ttf"]
```

---

## Architecture Tests

`tests/test_font_architecture.py` contains 10 tests across 3 test classes:

`tests/test_font_architecture.py` 包含 10 个测试，分为 3 个测试类:

### TestNoSystemFonts (2 tests)

| Test | Description |
|------|-------------|
| No system font paths in UI source | Scans all `.py` files in `inkpi/ui/`, forbids system font paths |
| No system font paths in Display source | Scans all `.py` files in `inkpi/display/`, forbids system font paths |

!!! tip "Policy Enforcement"
    These two tests are architecture guards. If anyone introduces a system
    font path, CI fails immediately. No manual code review needed to catch
    this class of problem.

    这两个测试是架构守卫。任何人在代码中引入系统字体路径，
    CI 会立即失败。不需要人工 code review 来检查这类问题。

### TestBundledFonts (5 tests)

| Test | Description |
|------|-------------|
| All font files exist | 7 TTF files all present in `inkpi/fonts/` |
| All fonts loadable | Each TTF opens with `ImageFont.truetype()` |
| Text fonts multi-size load | 4 CN fonts loadable at 16/20/24/28 px |
| Icon font loadable | SymbolsNerdFontMono loads correctly |
| Emoji font loadable | NotoEmoji loads correctly |

### TestFontLoadingFunction (3 tests)

| Test | Description |
|------|-------------|
| `_load_font` returns FreeTypeFont | Confirms correct return type |
| `_load_icon_font` returns FreeTypeFont | Confirms correct return type |
| All weights loadable | regular/medium/semibold/bold all available |

---

## Font Manifest

| File | Size | Purpose | License |
|------|------|---------|---------|
| `MapleMono-CN-Regular.ttf` | 18 MB | Body text regular (incl. CJK) | SIL OFL 1.1 |
| `MapleMono-CN-Medium.ttf` | 18 MB | Body text medium | SIL OFL 1.1 |
| `MapleMono-CN-SemiBold.ttf` | 18 MB | Body text semibold | SIL OFL 1.1 |
| `MapleMono-CN-Bold.ttf` | 18 MB | Body text bold | SIL OFL 1.1 |
| `MapleMono.ttf` | 259 KB | Latin-only fallback | SIL OFL 1.1 |
| `SymbolsNerdFontMono-Regular.ttf` | 2.5 MB | Icons (weather/status/developer) | MIT |
| `NotoEmoji-Regular.ttf` | ~890 KB | Unicode emoji | SIL OFL 1.1 |

!!! note "Package Size"
    Total font size is about 76 MB, with the four MapleMono-CN variants
    accounting for 72 MB. This is large for an embedded device, but e-ink
    dashboard deployments sync once and don't transfer fonts frequently.
    Subsetting could reduce size in the future.

    字体总计约 76 MB，其中 MapleMono-CN 四个变体占 72 MB。
    对于嵌入式设备来说偏大，但 e-ink 仪表盘场景下不会频繁传输，
    部署时一次性同步即可。后续可考虑 subset 裁剪减小体积。

---

## Deliverables

| Deliverable | Description | Type |
|-------------|-------------|------|
| `inkpi/fonts/` directory | 7 TTF + 2 license files | Resources |
| `drawing.py` unified loading | `_load_font()` + `_load_icon_font()` | Source |
| 5 duplicate implementations removed | Panel files now import from drawing | Refactor |
| System fallback eliminated | All `/usr/share/fonts/` paths deleted | Refactor |
| `importlib.resources` | Path resolution no longer depends on CWD | Source |
| `pyproject.toml` | package-data configuration | Config |
| Architecture tests | `test_font_architecture.py` (10 tests) | Tests |

---

## Verification Results

| Check | Result |
|-------|--------|
| All pytest pass | ✅ 101 tests pass |
| Architecture tests pass | ✅ 10 font tests pass |
| ruff check clean | ✅ clean |
| compileall no syntax errors | ✅ clean |
| No system font paths remaining | ✅ Enforced by architecture tests |
| All fonts loadable | ✅ 7/7 TTF loadable |

!!! success "Phase 5 Complete"
    All fonts bundled in `inkpi/fonts/`, loaded via `importlib.resources`.
    Unified loading entry point eliminated 6 duplicate code paths.
    Architecture tests prevent system font path regressions.
    Rendering output on macOS and Pi is now identical.

    全部字体内置在 `inkpi/fonts/` 内，通过 `importlib.resources` 加载。
    统一加载入口消除了 6 处重复代码。架构测试防止系统字体路径回退。
    macOS 和 Pi 上的渲染输出现在完全一致。
