# `inkpi-display`

`inkpi-display` is the sole SPI/GPIO and Waveshare panel owner. It consumes
complete PNG frames from `inkpi-api` and applies the longevity-first refresh
policy in `backend/src/inkpi/display/`.

```text
inkpi-api ──revision + PNG──> DisplayPullLoop ──> DisplayEngine ──> WaveshareBackend
```

## Pull loop

The service polls `/api/display/revision`, debounces a new revision, downloads
`/api/display/image`, converts it to grayscale, and submits the complete frame
with page identity `eink`. Accepted refresh telemetry is posted back to the API.

Default runtime values are:

| Setting | Default |
|---|---:|
| Poll interval | 2 seconds |
| Debounce interval | 1 second |
| API URL | `http://127.0.0.1:8080` |

Set `INKPI_API_URL`, `INKPI_DISPLAY_POLL_SECONDS`,
`INKPI_DISPLAY_DEBOUNCE_SECONDS`, and `INKPI_DISPLAY_TOKEN` as needed.

## Refresh decisions

| Condition | Result |
|---|---|
| Startup, recovery, page change | Full refresh |
| Grayscale-only change | Full refresh |
| Changed ratio above `0.12` | Full refresh |
| No meaningful change below `0.0005` | Skip |
| 50 consecutive partial refreshes | Full refresh |
| Repeated changes in one region reach 30 | Region repair |
| Other small monochrome change | Partial refresh |

Dirty regions receive eight pixels of padding and are aligned to eight-pixel
boundaries. The policy values come from `DisplayConfig` and can be overridden
in `~/.config/inkpi/config.json`.

The engine owns its previous accepted frame, partial-refresh streak, regional
repair counters, and queue. A failed refresh clears this state and forces full
recovery on the next accepted frame.

## Simulation and hardware

Run against a local API from `backend/`:

```bash
uv run inkpi-display --api-url http://127.0.0.1:8080
```

On a non-Pi machine, the adapter enters simulation mode while preserving the
same pull, decision, and telemetry behavior. Simulation does not validate
SPI/GPIO, panel waveform behavior, ghosting, or physical readability; those
require deployment to `meta_pi`.
