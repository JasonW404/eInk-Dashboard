# inkpi-display

`inkpi-display` is the sole SPI/GPIO and physical-panel owner.

```text
inkpi-api ──revision + complete PNG──> DisplayPullLoop
                                            │
                                            v
                                      DisplayEngine
                                            │
                                            v
                                     WaveshareBackend
```

The pull loop polls `/api/display/revision`, debounces changes, downloads
`/api/display/image`, and submits a complete logical frame. The existing
longevity-first engine then chooses:

| Condition | Action |
|---|---|
| Startup, recovery, page/grayscale/large change | Full |
| No meaningful change | Skip |
| Partial streak limit | Full |
| Region repair threshold | Region repair |
| Small monochrome same-page change | Partial |

Dirty regions are aligned to eight-pixel boundaries. Failed refreshes clear the
previous-frame state so the next accepted frame uses full recovery.

Run against a local API:

```bash
cd backend
uv run inkpi-display --api-url http://127.0.0.1:8080
```

On a non-Pi machine the Waveshare adapter enters simulation mode while keeping
the same refresh policy and telemetry behavior.
