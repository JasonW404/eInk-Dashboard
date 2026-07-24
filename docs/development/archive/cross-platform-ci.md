# Phase 4: Cross-Platform Verification & CI

> **Status:** ✅ Done
> **Back to:** [Development Plan](../plan.md)

---

## Problem Statement

InkPi is developed on macOS and deployed on Raspberry Pi. The display engine
depends on SPI/GPIO hardware, so developers cannot verify rendering output
or refresh decisions locally. Every change required a Pi deployment to
confirm results, which made iteration slow.

InkPi 在 macOS 上开发，在 Raspberry Pi 上部署。显示引擎依赖 SPI/GPIO
硬件，开发者在本地无法验证渲染输出和刷新决策是否正确。
每次改动都需要部署到 Pi 上才能确认效果，开发效率很低。

Core pain points:

- Display driver (`inkpi/display/`) directly operates SPI/GPIO, cannot run on macOS
- Rendering results are only visible on the physical panel, no offline verification
- No CI pipeline, code quality depends on manual review
- Rendering tests used golden image comparison, cross-platform pixel differences caused false failures

---

## Solution Overview

Phase 4 was split into 5 sub-tasks, building a complete offline
verification system step by step:

将 Phase 4 拆分为 5 个子任务，逐步建立完整的离线验证体系:

| # | Sub-task | Core Output |
|---|----------|-------------|
| 4.1 | FileBackend | Frame recorder backend, writes each frame to PNG |
| 4.2 | e-ink dithering preview | `--eink-preview` flag, simulates 4-gray e-ink effect |
| 4.3 | GitHub Actions CI | test + lint + smoke three-stage pipeline |
| 4.4 | ruff static analysis | Added to dev deps, unified code style |
| 4.5 | Structured rendering tests | Structural assertions replace golden image comparison |

---

## 4.1 FileBackend

### Design Goal

Provide a hardware-free frame recording backend. Each rendered frame is
written to a PNG file so developers can inspect refresh decisions locally.

提供一个不依赖硬件的帧记录后端。每帧渲染结果写入 PNG 文件，
开发者可以在本地查看刷新决策的实际效果。

### Implementation

- **File:** `inkpi/display/file_backend.py`
- **Interface:** Same method signatures as the hardware backend (`init`, `display_frame`, `sleep`)
- **Frame counter:** Built-in counter, filenames include sequence number (`frame_0001.png`)
- **Directory management:** Auto-creates output directory, supports custom paths
- **Metadata:** Logs refresh type (full/partial/skip) for each frame

### Test Coverage

13 tests covering all public methods:

| Test Scenario | Description |
|---------------|-------------|
| Initialization | Directory creation, counter reset to zero |
| Frame writing | PNG output, filename format, counter increment |
| Refresh types | full/partial/skip each recorded separately |
| Edge cases | Empty frame, repeated init, sleep behavior |

---

## 4.2 e-ink Dithering Preview

### Design Goal

Simulate the 4-level grayscale effect of an e-ink panel on the dev
machine, letting developers quickly verify visual quality of rendered output.

在开发机上模拟墨水屏的 4 级灰度效果，帮助开发者快速验证
渲染输出的视觉质量。

### Implementation

- **File:** `inkpi/ui/eink_preview.py`
- **CLI entry:** `inkpi-preview overview --mock-data --eink-preview`
- **Algorithm:** Pure Pillow Floyd-Steinberg error diffusion dithering
- **Quantization:** Maps 256 gray levels to 4 levels (0, 85, 170, 255)
- **No external deps:** No numpy or OpenCV, only Pillow

!!! info "Why Floyd-Steinberg"
    4-gray e-ink panels produce output close to error diffusion dithering.
    Floyd-Steinberg is simple to implement with pure Pillow,
    no extra image processing dependencies needed.

### Test Coverage

6 tests:

| Test Scenario | Description |
|---------------|-------------|
| Output size | Matches input (800x480) |
| Output mode | Grayscale mode (L) |
| Palette distribution | Pixel values contain only 4 gray levels |
| Pure white input | All-white image stays unchanged |
| Pure black input | All-black image stays unchanged |
| Gradient input | Gray level distribution is reasonable |

---

## 4.3 GitHub Actions CI

### Design Goal

Run tests, lint, and smoke tests automatically on every push and PR
to maintain code quality.

每次 push 和 PR 自动运行测试、lint 和冒烟测试，确保代码质量。

### Workflow Structure

```
.github/workflows/ci.yml
```

Three jobs run sequentially:

| Job | Runner | Content |
|-----|--------|---------|
| **test** | macOS + Ubuntu (matrix) | `uv run pytest -q` |
| **lint** | Ubuntu | `uv run ruff check inkpi tests` |
| **smoke** | Ubuntu | `scripts/smoke_test.sh` dual-service smoke test |

!!! note "Why matrix for tests"
    macOS and Ubuntu Python environments differ (especially C extension
    compilation). Matrix strategy ensures both platforms pass.

### smoke_test.sh

- **File:** `scripts/smoke_test.sh`
- **Flow:** Start `inkpi-display` and `inkpi-core`, wait for ready, send control commands, verify responses, clean up processes
- **Timeout:** Each stage has independent timeout control to prevent CI hangs

---

## 4.4 ruff Static Analysis

### Design Goal

Introduce a unified code style checker to replace manual style debates
in code review.

引入统一的代码风格检查工具，替代手动 code review 中的风格争论。

### Implementation

- Added to `[project.optional-dependencies] dev` group
- Configured in `pyproject.toml` under `[tool.ruff]`
- CI lint job runs `uv run ruff check inkpi tests`
- Initial config uses relaxed rules, tightened incrementally

---

## 4.5 Structured Rendering Tests

### Why Not Golden Image

Golden image comparison (pixel-level diff) has many problems in
cross-platform scenarios:

Golden image 对比 (像素级 diff) 在跨平台场景下问题很多:

- macOS and Linux Pillow rendering produces minor pixel differences
- Font version differences cause text rendering inconsistencies
- Any UI tweak invalidates the golden image, high maintenance cost

### Alternative: Structural Assertions

A set of structural assertions validates key properties of rendered output:

用一组结构性断言验证渲染输出的关键属性:

| Assertion Type | Check |
|----------------|-------|
| Size | Output image must be 800x480 |
| Mode | Must be grayscale mode (L) |
| Non-blank | Image must not be all-white or all-black |
| Gray distribution | All 4 gray levels have reasonable proportions |
| Content regions | Specific regions contain non-background pixels |

### Test Coverage

- **File:** `tests/test_rendering_structure.py`
- **Test count:** 8
- **Scope:** overview page and mock data scenarios

---

## Deliverables

| Deliverable | File Path | Type |
|-------------|-----------|------|
| FileBackend | `inkpi/display/file_backend.py` | Source |
| FileBackend tests | `tests/test_file_backend.py` (13 tests) | Tests |
| e-ink dithering preview | `inkpi/ui/eink_preview.py` | Source |
| e-ink preview tests | `tests/test_eink_preview.py` (6 tests) | Tests |
| CI workflow | `.github/workflows/ci.yml` | CI |
| Smoke test script | `scripts/smoke_test.sh` | Script |
| ruff config | `pyproject.toml [tool.ruff]` | Config |
| Structured rendering tests | `tests/test_rendering_structure.py` (8 tests) | Tests |

---

## Verification Results

| Check | Result |
|-------|--------|
| All pytest pass | ✅ 101 tests pass |
| ruff check clean | ✅ clean |
| compileall no syntax errors | ✅ clean |
| CI macOS job | ✅ pass |
| CI Ubuntu job | ✅ pass |
| CI smoke job | ✅ pass |

!!! success "Phase 4 Complete"
    开发者在 macOS 上可以完成 90% 的验证工作:
    FileBackend 离线查看帧输出，e-ink 预览模拟墨水屏效果，
    结构化测试替代 golden image，CI 流水线自动守护代码质量。
