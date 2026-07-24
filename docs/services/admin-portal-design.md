# InkPi Admin Portal Design

## Purpose

`inkpi-admin` is the local web administration surface for the Pi appliance. It
serves people who are physically near the device, often while network access is
broken or being reconfigured. The portal must therefore behave like a reliable
appliance control panel: dense, predictable, fast to scan, and hard to lock
oneself out of.

The admin portal is not a display renderer and does not own SPI/GPIO. It
consumes core contracts for dashboard, display, system, and read-only network
state. Privileged network mutations are delegated to a narrow helper with an
allowlisted command surface.

## Access Methods

The portal must be reachable through every supported local management path:

- Direct Ethernet or LAN access.
- Direct hotspot Wi-Fi access from devices joined to the Pi access point.
- Optional hidden hotspot access when the Pi already has internet through
  Ethernet or tunnel and the hotspot is kept for maintenance or sharing.

The portal must show all active addresses because the correct URL can change
after Wi-Fi configuration. When a change may move the browser to a different
network, the portal keeps the current hotspot/session alive until the new path
is confirmed and displayed.

## Runtime Ownership

- `inkpi-admin`: HTTP service, static assets, page/API routes, auth/session
  handling, and user-facing workflow state.
- `inkpi-core`: dashboard scheduling, page controls, display status proxy, and
  configuration persistence for non-secret app settings.
- `inkpi-management`: read-only system and network facts.
- `inkpi-network-helper`: privileged NetworkManager/hotspot/NAT mutations.
- `inkpi-display`: sole physical display owner.

`inkpi-admin` talks to `inkpi-core` through `InkPiClient`. It talks to
`inkpi-network-helper` through a small local IPC contract. It must never expose
an arbitrary shell bridge.

## Information Architecture

The portal uses a classic modern admin layout:

- Fixed left navigation on desktop.
- Collapsible top navigation drawer on mobile.
- Top status bar with internet state, active access path, device address, and
  service health.
- Main content area with dense tables, forms, and status panels.

Primary sections:

- **Overview**: appliance summary, access path, service health, quick actions,
  and recent events.
- **Network**: Ethernet, Wi-Fi, hotspot, tunnel, and recovery policy controls.
- **Dashboard**: browser version of dashboard pages, page controls, rotation
  settings, display status, and manual render/display actions.
- **System**: CPU, memory, disk, temperature, uptime, version, and service
  restart controls.
- **Logs**: bounded non-secret event stream from admin, core, display, and
  network helper.
- **Settings**: hostname, admin auth, hotspot policy defaults, safe advanced
  options, and update channel later.

## Overview Page

The Overview page is the first screen after authentication. It answers four
questions without requiring navigation:

- Is the Pi reachable and healthy?
- How am I connected to it?
- Does it have internet?
- Is the e-ink dashboard running?

Layout:

- Status strip: Internet, access path, current address, version.
- Service row: core, display, admin, network helper.
- Network summary: Wi-Fi SSID, Ethernet state, hotspot mode, client count.
- Dashboard summary: active page, enabled pages, next rotation, last refresh.
- System summary: uptime, CPU, memory, disk, temperature.
- Recent events: last 10 important admin/network/display events.

Primary actions:

- Open Network.
- Open Dashboard preview.
- Refresh display now.
- Restart dashboard services with confirmation.

## Network Page

The Network page is the most important screen and should not hide state behind
wizard-only flows. It uses visible sections and staged apply progress.

Top status cards:

- Internet: online/offline, probe target, last check.
- Active access: Ethernet, Wi-Fi, hotspot, tunnel, or mixed.
- Pi addresses: every IPv4/IPv6 address grouped by interface.
- Hotspot: off, visible, hidden, sharing, clients.

Main sections:

- **Connection Priority**
  - Ethernet.
  - Tunnel.
  - Wi-Fi.
  - Recovery hotspot.

- **Wi-Fi**
  - Current SSID and signal when connected.
  - Known networks with last success/failure.
  - Scan results with signal, security, and known/new badges.
  - Connect form for selected SSID.
  - Manual SSID entry for hidden networks.

- **Hotspot**
  - Mode: off, visible recovery, hidden maintenance.
  - SSID, channel, client count, gateway address.
  - Internet sharing status.
  - Controls: enable now, disable now, rotate password, show QR code.

- **Recovery**
  - Current policy decision.
  - Failed Wi-Fi attempts and last failure reason.
  - Retry known Wi-Fi.
  - Forget a failed network.
  - Restore recovery hotspot.

Wi-Fi credential submission is staged:

1. User submits credentials.
2. Hotspot remains active.
3. Helper attempts connection and reports progress.
4. Portal confirms internet and shows the new LAN address.
5. Hotspot policy is applied after the user has a working path or after a
   timeout fallback.

## Network Policy

The policy state machine is implemented as a pure decision layer before any
helper writes. Current states:

- `offline_recovery_hotspot`
- `online_ethernet_hotspot`
- `online_tunnel_hotspot`
- `online_wifi`
- `wifi_connecting`
- `wifi_failed_recovery_hotspot`
- `unknown`

Hotspot is enabled when:

- There is no usable internet connection. The hotspot is visible and used for
  Wi-Fi setup or direct Pi control.
- There is internet through Ethernet or tunnel. The hotspot may be hidden and
  may share that upstream connection.
- Configured Wi-Fi fails after the retry budget, defaulting to 3 attempts. The
  recovery hotspot is restored.

Hotspot is disabled or deprioritized when:

- Wi-Fi is connected and has usable internet.
- A known Wi-Fi network is available, but only after a staged connection flow
  confirms that the new access path works.
- A user submits Wi-Fi credentials, with hotspot kept alive until success is
  confirmed or failure restores recovery mode.

## Dashboard Page

The Dashboard page provides a browser version of the e-ink appliance state,
not a marketing site.

Layout:

- Preview area showing the current page as an 800x480 image or web-rendered
  equivalent.
- Page table with enabled state, health, last error, and last render time.
- Rotation controls: interval, current page, next rotation.
- Display controls: refresh now, sleep panel, wake panel later when supported.
- Display telemetry: last action, reason, full/partial/skipped counts, pending
  frames, consecutive failures.

The dashboard page controls use core contracts and must preserve the invariant
that at least one dashboard page remains enabled.

The current implementation serves a deterministic mock overview preview at
`GET /api/dashboard/preview/overview.png` and embeds it in the dashboard
section. It intentionally avoids live collectors in HTTP request handling.
Future live preview should be exposed through core-owned render contracts so
admin never bypasses dashboard ownership or display refresh policy.

## System Page

The System page is operational but restrained:

- CPU, memory, disk, temperature, load, uptime.
- Process health for admin, core, display, network helper.
- Version, git revision/build metadata later, Python version.
- Restart controls for admin/core/display with confirmations.
- Shutdown/reboot controls behind a stronger confirmation later.

## Logs Page

Logs are an event stream, not an unrestricted journal browser.

- Show recent bounded events.
- Filter by service and severity.
- Redact secrets before events are stored or displayed.
- Include network policy decisions and helper results.
- Never display Wi-Fi passwords, tokens, cookies, or API keys.

The current implementation exposes a bounded in-memory admin event stream at
`GET /api/events`. Network operation submissions and dashboard page mutations
record events with recursively redacted details. This is intentionally separate
from raw systemd journals.

## Settings Page

Settings hold non-secret appliance preferences:

- Device hostname.
- Portal auth policy.
- Hotspot SSID and policy defaults.
- Whether hidden maintenance hotspot is allowed when upstream is online.
- Whether hotspot internet sharing is allowed.
- Dashboard rotation defaults.

Secrets such as Wi-Fi credentials and hotspot passwords are handled through
NetworkManager or a secret store owned by the helper, not editable JSON.

## API Shape

Read-only admin endpoints:

- `GET /api/status`
- `GET /api/network`
- `GET /api/dashboard`
- `GET /api/display`
- `GET /api/system`
- `GET /api/events`

Network mutation endpoints:

- `POST /api/network/wifi/scan`
- `POST /api/network/wifi/connect`
- `POST /api/network/wifi/forget`
- `POST /api/network/hotspot/enable`
- `POST /api/network/hotspot/disable`
- `POST /api/network/hotspot/rotate-password`
- `POST /api/network/policy/reconcile`

Dashboard mutation endpoints:

- `POST /api/dashboard/pages/{page_id}/enable`
- `POST /api/dashboard/pages/{page_id}/disable`
- `POST /api/dashboard/refresh`

All mutations return an operation ID and progress state when work may outlive
the request.

Dashboard page enable/disable routes are implemented through the existing core
contract. Core remains responsible for validating page IDs and rejecting
requests that would disable the final enabled page. Dashboard refresh remains a
future mutation because display refresh ownership and urgency rules must stay
inside core/display contracts.

The current implementation wires network mutation endpoints to an in-memory
allowlisted operation queue. This validates payloads, returns operation IDs,
and records safe metadata without touching NetworkManager. The real privileged
helper must keep the same narrow action surface and must not accept arbitrary
commands. Wi-Fi passwords are accepted only by the future helper boundary and
must never be stored in admin operation history.

The no-build HTML shell includes guarded controls for Wi-Fi scan/connect,
hotspot enable/disable, and dashboard page enable/disable. Controls call the
same JSON endpoints as external clients and require the configured admin token.

`inkpi/admin/network_helper.py` defines the current dry-run NetworkManager
planner. It converts allowlisted operations into explicit `nmcli` command
vectors for review and tests, but does not execute them. Secret-bearing steps
are marked as requiring a transient secret channel; real passwords must not be
placed in argv, JSON responses, events, or logs.

## Security And Safety

- Local-only by default.
- Authentication required before mutations.
- CSRF protection for browser sessions.
- No arbitrary command execution.
- No secrets in logs, JSON config, screenshots, or tests.
- Apply network changes asynchronously.
- Keep a known working admin access path during Wi-Fi transitions.
- Prefer explicit confirmation for actions that restart services, disable
  hotspot, or may interrupt the current session.

Current mutation protection is token based: callers must provide
`X-InkPi-Admin-Token` or `Authorization: Bearer` with the configured admin
token. Requests with browser `Origin` headers are rejected unless the origin
host matches the admin service host. Later cookie-backed sessions must preserve
the same mutation boundary and add per-session CSRF tokens before enabling
forms that issue POST requests from the portal UI.

## Implementation Phases

1. ✅ Admin foundations: package, design contracts, network policy evaluator,
   static layout, read-only API.
2. ✅ Dashboard browser page: page controls, preview rendering, display status.
3. ✅ Network helper contract: dry-run planner, privileged helper backend
   (`helper_client.py`, `privileged.py`), Unix socket IPC, allowlisted operations.
4. ✅ Recovery hotspot: staged Wi-Fi connection flow (submit, confirm, fail),
   retry budget, automatic fallback, recovery tracking.
5. ✅ Hidden maintenance hotspot: upstream sharing over Ethernet/tunnel,
   iptables NAT rules, ip_forward, cleanup on disable.
6. ✅ System operations: service restarts (`/api/system/restart/{service}`),
   settings save/get, session auth with CSRF tokens, bounded event logs.

All phases keep the existing display/core/dashboard ownership boundaries intact.
