# Frontend and eInk UI

The `frontend/` project is a single Bun/Vite/React application with two HTML
entry points. Both use the API client in `frontend/src/api/client.ts`.

| Entry point | Source | Purpose |
|---|---|---|
| `index.html` | `src/app/` | Interactive browser management UI |
| `eink.html` | `src/eink/` | Deterministic fixed-size display frame |

The production build is written to `frontend/dist/` and served by `inkpi-api`.

## Web application

The browser application has three client-side routes:

| Route | Implemented behavior |
|---|---|
| `/` | Device health, Codex/GitHub summary, TODO summary, and current eInk PNG preview |
| `/todo` | Create, rename, complete, delete, reorder, and toggle eInk visibility |
| `/settings` | System facts and hotspot enable, update, or disable controls |

The desktop layout uses a sidebar; the responsive layout switches to mobile
header and navigation elements. Hotspot mutations send the admin token entered
by the user directly to the API and do not persist it in application state.

## eInk view

The eInk root is exactly 800×480 pixels and has no scrolling. It displays:

- product title, current date, display revision, and online/offline state;
- up to eight TODOs marked for eInk display;
- Codex weekly usage and reset time;
- GitHub monthly commits and pull requests;
- the last seven contribution days, ending with today;
- hotspot SSID and Wi-Fi QR code when active, or `HOTSPOT OFF`.

The contribution calendar uses only empty, hatched, and solid cells. It does
not encode activity through subtle colors because the target panel has four
gray levels.

## Rendering contract

`PlaywrightDisplayRenderer` opens:

```text
/eink.html?revision=<current-revision>
```

It uses an 800×480 viewport, waits for
`.eink-display[data-eink-ready='true']`, waits for bundled fonts, and
screenshots that element only. A renderer failure must leave the previous
physical frame intact.

The eInk page may call `/api/display/context`; that endpoint is loopback-only
because it can contain an ephemeral Wi-Fi QR payload. Normal remote Web clients
cannot read it.

## Styling constraints

- Keep the eInk root at exactly 800×480.
- Use bundled frontend fonts; rendering must not depend on host fonts.
- Prefer black, white, borders, hatching, and clear hierarchy over subtle color.
- Keep important text readable on the physical 4.26-inch panel.
- Do not add animations or asynchronous content that can continue changing
  after the ready marker is set.
- React renders logical content only; it never chooses a display refresh mode.

After changing the eInk view, run `bun run build`, the repository smoke test,
and inspect the generated frame before physical-panel deployment.
