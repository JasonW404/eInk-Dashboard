"""Small stdlib HTTP server for the local InkPi admin portal."""

from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from inkpi.admin.auth import AdminAuthError, AdminAuthPolicy, extract_bearer_token
from inkpi.admin.preview import render_mock_page_png, render_page_preview
from inkpi.admin.service import AdminService
from inkpi.client import DEFAULT_CORE_SOCKET, InkPiClient

DEFAULT_ADMIN_HOST = "127.0.0.1"
DEFAULT_ADMIN_PORT = 8081


def run_admin_service(
    *,
    host: str = DEFAULT_ADMIN_HOST,
    port: int = DEFAULT_ADMIN_PORT,
    core_socket: str | Path = DEFAULT_CORE_SOCKET,
    auth_policy: AdminAuthPolicy | None = None,
) -> None:
    """Run the local admin web service."""

    client = InkPiClient(core_socket)
    service = AdminService(client)
    server = build_admin_server(host, port, service, auth_policy=auth_policy, core_client=client)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def build_admin_server(
    host: str,
    port: int,
    service: AdminService,
    *,
    auth_policy: AdminAuthPolicy | None = None,
    core_client: InkPiClient | None = None,
) -> ThreadingHTTPServer:
    """Build an admin HTTP server around a service instance."""

    policy = auth_policy or AdminAuthPolicy.from_environment()

    class AdminHandler(_AdminHandler):
        service_factory = staticmethod(lambda: service)
        auth_policy = policy
        preview_client = core_client

    class ReusableServer(ThreadingHTTPServer):
        allow_reuse_address = True

    return ReusableServer((host, port), AdminHandler)


class _AdminHandler(BaseHTTPRequestHandler):
    service_factory: Callable[[], AdminService]
    auth_policy: AdminAuthPolicy
    preview_client: InkPiClient | None = None
    server_version = "InkPiAdmin/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path

        if route == "/api/status":
            payload = self.service_factory().status_payload()
            payload["auth"] = {"mutation_token_configured": self.auth_policy.configured}
            self._send_json(payload)
            return

        if route == "/api/network":
            snapshot = self.service_factory().snapshot()
            self._send_json(
                {
                    "network": snapshot.network,
                    "policy": snapshot.network_policy,
                    "summary": snapshot.summary,
                    "recovery": snapshot.recovery,
                }
            )
            return

        if route == "/api/dashboard":
            snapshot = self.service_factory().snapshot()
            self._send_json(
                {
                    "dashboard": snapshot.dashboard,
                    "pages": snapshot.pages,
                    "display": snapshot.display,
                }
            )
            return

        if route.startswith("/api/dashboard/preview/") and route.endswith(".png"):
            page_id = route.removeprefix("/api/dashboard/preview/").removesuffix(".png")
            try:
                if self.preview_client is not None:
                    self._send_png(render_page_preview(page_id, self.preview_client))
                else:
                    self._send_png(render_mock_page_png(page_id))
            except ValueError as error:
                self._send_json({"ok": False, "error": str(error)}, status=HTTPStatus.NOT_FOUND)
            return

        if route == "/api/display":
            self._send_json(self.service_factory().snapshot().display)
            return

        if route == "/api/system":
            self._send_json(self.service_factory().snapshot().system)
            return

        if route == "/api/events":
            service = self.service_factory()
            payload = service.events_payload()
            payload["network_operations"] = service.network_operations_payload()["operations"]
            self._send_json(
                payload
            )
            return

        if route == "/api/settings":
            snapshot = self.service_factory().snapshot()
            self._send_json(
                {
                    "hostname": snapshot.hostname,
                    "auth": {"mutation_token_configured": self.auth_policy.configured},
                    "hotspot": {
                        "mode": snapshot.network_policy.get("hotspot_mode", "off"),
                    },
                    "dashboard": {
                        "rotation_interval_seconds": snapshot.dashboard.get(
                            "rotation_interval_seconds", 300
                        ),
                    },
                }
            )
            return

        if route in {"/", "/network", "/dashboard", "/system", "/logs", "/settings"}:
            self._send_html(render_admin_html(self.service_factory().snapshot(), active_route=route))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        operation = _NETWORK_POST_ROUTES.get(route)

        try:
            self._validate_mutation_auth()

            if route == "/api/network/wifi/confirm":
                self.service_factory().confirm_staged_wifi()
                self._send_json({"ok": True, "message": "Wi-Fi connection confirmed"})
                return

            if route == "/api/network/wifi/fail":
                self.service_factory().fail_staged_wifi()
                self._send_json(
                    {"ok": True, "message": "Wi-Fi connection failed, recovery hotspot restored"}
                )
                return

            if operation is not None:
                payload = self._read_json_body()
                result = self.service_factory().submit_network_operation(operation, payload)
                if operation == "wifi_connect" and isinstance(payload, dict):
                    ssid = payload.get("ssid")
                    if isinstance(ssid, str) and ssid.strip():
                        self.service_factory().set_staged_wifi(ssid.strip())
                self._send_json({"ok": True, "operation": result}, status=HTTPStatus.ACCEPTED)
                return

            dashboard_mutation = _dashboard_page_mutation(route)
            if dashboard_mutation is not None:
                page_id, enabled = dashboard_mutation
                result = self.service_factory().set_dashboard_page_enabled(page_id, enabled)
                status = HTTPStatus.OK if result["accepted"] else HTTPStatus.BAD_REQUEST
                self._send_json({"ok": result["accepted"], "result": result}, status=status)
                return

            if route == "/api/dashboard/refresh":
                result = self.service_factory().trigger_display_refresh()
                self._send_json({"ok": True, "result": result})
                return

            if route.startswith("/api/system/restart/"):
                service_name = route.removeprefix("/api/system/restart/")
                if service_name not in {"core", "display", "admin"}:
                    self._send_json(
                        {"ok": False, "error": f"unknown service: {service_name}"},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._send_json(
                    {"ok": True, "message": f"Restart queued for {service_name}"}
                )
                return

            if route == "/api/settings":
                self._read_json_body()
                self._send_json({"ok": True, "message": "Settings saved"})
                return
        except AdminAuthError as error:
            self._send_json({"ok": False, "error": str(error)}, status=HTTPStatus(error.status))
            return
        except ValueError as error:
            self._send_json({"ok": False, "error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _validate_mutation_auth(self) -> None:
        token = self.headers.get("X-InkPi-Admin-Token", "").strip() or None
        token = token or extract_bearer_token(self.headers.get("Authorization"))
        self.auth_policy.validate_mutation(
            token=token,
            origin=self.headers.get("Origin"),
            host=self.headers.get("Host"),
        )

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("request body must be JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _send_json(self, payload: dict, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_png(self, body: bytes) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Portal HTML rendering
# ---------------------------------------------------------------------------


def render_admin_html(snapshot, *, active_route: str = "/") -> str:
    """Render the current no-build portal shell."""

    content = _render_page_content(snapshot, active_route)
    return _render_shell(snapshot, active_route=active_route, content=content)


def _render_page_content(snapshot, active_route: str) -> str:
    renderers = {
        "/": _render_overview_page,
        "/network": _render_network_page,
        "/dashboard": _render_dashboard_page,
        "/system": _render_system_page,
        "/logs": _render_logs_page,
        "/settings": _render_settings_page,
    }
    return renderers.get(active_route, _render_overview_page)(snapshot)


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------


def _render_shell(snapshot, *, active_route: str, content: str) -> str:
    sections = "\n".join(_nav_item(section, active_route) for section in snapshot.sections)
    title = _esc(_title_for_route(snapshot.sections, active_route))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InkPi Admin</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #171717;
      --muted: #64645e;
      --line: #d9d9d2;
      --accent: #205f72;
      --warn: #8a4b00;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 220px 1fr;
    }}
    nav {{
      border-right: 1px solid var(--line);
      background: #ededeb;
      padding: 18px 14px;
    }}
    .brand {{
      font-weight: 700;
      font-size: 18px;
      margin: 0 0 18px;
    }}
    .nav-item {{
      display: block;
      color: var(--ink);
      text-decoration: none;
      padding: 9px 10px;
      border-radius: 6px;
      margin-bottom: 3px;
    }}
    .nav-item.active {{
      background: var(--ink);
      color: white;
    }}
    main {{ padding: 18px 22px 28px; }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: baseline;
      margin-bottom: 16px;
    }}
    h1 {{ margin: 0; font-size: 24px; }}
    .host {{ color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(110px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .card, section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .card {{ padding: 10px 12px; min-height: 64px; }}
    .label {{ color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
    .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    .content {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
      gap: 14px;
    }}
    section {{ padding: 14px; margin-bottom: 14px; }}
    h2 {{ margin: 0 0 10px; font-size: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 7px 6px; border-bottom: 1px solid var(--line); }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 600; }}
    code {{ background: #eeeeea; border: 1px solid var(--line); border-radius: 4px; padding: 1px 4px; }}
    .notice {{ color: var(--warn); }}
    .token {{
      display: flex;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
    }}
    input, select, button {{
      font: inherit;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 8px;
      background: white;
      color: var(--ink);
    }}
    button {{
      background: var(--ink);
      color: white;
      cursor: pointer;
    }}
    button.secondary {{
      background: white;
      color: var(--ink);
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-top: 10px;
    }}
    .action-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(160px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }}
    .action-grid form {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfbf8;
    }}
    .action-grid label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 5px;
    }}
    .action-grid input, .action-grid select {{
      width: 100%;
      margin-bottom: 8px;
    }}
    .result {{
      min-height: 20px;
      color: var(--muted);
      margin-bottom: 10px;
    }}
    .preview {{
      margin-bottom: 12px;
      border: 1px solid var(--line);
      background: #f1f1ec;
      border-radius: 8px;
      padding: 8px;
    }}
    .preview img {{
      display: block;
      width: 100%;
      max-width: 800px;
      height: auto;
      aspect-ratio: 5 / 3;
      border: 1px solid var(--line);
    }}
    .filter-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }}
    .filter-bar label {{
      color: var(--muted);
      font-size: 12px;
      margin-right: 4px;
    }}
    .filter-bar select {{
      min-width: 120px;
    }}
    .settings-form {{
      max-width: 480px;
    }}
    .settings-form label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
      margin-top: 12px;
    }}
    .settings-form input, .settings-form select {{
      width: 100%;
    }}
    .settings-form .readonly {{
      background: #f1f1ec;
      color: var(--muted);
    }}
    .restart-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(120px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }}
    .quick-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .quick-actions a {{
      display: inline-block;
      padding: 7px 14px;
      background: var(--ink);
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 13px;
    }}
    .quick-actions a.secondary-link {{
      background: white;
      color: var(--ink);
      border: 1px solid var(--line);
    }}
    @media (max-width: 780px) {{
      .shell {{ grid-template-columns: 1fr; }}
      nav {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .grid, .content {{ grid-template-columns: 1fr; }}
      .restart-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <nav>
      <p class="brand">InkPi Admin</p>
      {sections}
    </nav>
    <main>
      <header>
        <h1>{title}</h1>
        <div class="token">
          <label for="admin-token" title="Admin token required for write operations (connect Wi-Fi, enable hotspot, disable pages, restart services)">Admin Token</label>
          <input id="admin-token" type="password" autocomplete="current-password" placeholder="required for mutations" title="Enter the INKPI_ADMIN_TOKEN value. Read-only pages load without it.">
          <div class="host">{_esc(snapshot.hostname)}</div>
        </div>
      </header>
      <div id="action-result" class="result" role="status" aria-live="polite"></div>
      {content}
    </main>
  </div>
  <script>
    const result = document.getElementById('action-result');
    const tokenInput = document.getElementById('admin-token');

    async function submitMutation(endpoint, payload) {{
      const response = await fetch(endpoint, {{
        method: 'POST',
        headers: {{
          'Content-Type': 'application/json',
          'X-InkPi-Admin-Token': tokenInput.value.trim()
        }},
        body: JSON.stringify(payload || {{}})
      }});
      const data = await response.json();
      if (!response.ok || data.ok === false) {{
        throw new Error(data.error || data.result?.message || data.message || 'Request failed');
      }}
      return data;
    }}

    function formPayload(form) {{
      const data = {{}};
      new FormData(form).forEach((value, key) => {{
        if (String(value).length > 0) data[key] = value;
      }});
      return data;
    }}

    document.querySelectorAll('form[data-endpoint]').forEach((form) => {{
      form.addEventListener('submit', async (event) => {{
        event.preventDefault();
        if (form.dataset.confirm && !confirm(form.dataset.confirm)) return;
        result.textContent = 'Working...';
        try {{
          const data = await submitMutation(form.dataset.endpoint, formPayload(form));
          result.textContent = data.operation?.message || data.result?.message || data.message || 'Done';
        }} catch (error) {{
          result.textContent = error.message;
        }}
      }});
    }});

    document.querySelectorAll('button[data-endpoint]').forEach((button) => {{
      button.addEventListener('click', async () => {{
        if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
        result.textContent = 'Working...';
        try {{
          const data = await submitMutation(button.dataset.endpoint, {{}});
          result.textContent = data.result?.message || data.message || 'Done';
        }} catch (error) {{
          result.textContent = error.message;
        }}
      }});
    }});

    /* Logs page: client-side filtering and auto-refresh */
    const logsTable = document.getElementById('logs-table');
    if (logsTable) {{
      const serviceFilter = document.getElementById('log-service');
      const severityFilter = document.getElementById('log-severity');
      const autoRefresh = document.getElementById('log-auto-refresh');
      let cachedEvents = [];
      let interval = null;

      async function loadEvents() {{
        try {{
          const response = await fetch('/api/events');
          const data = await response.json();
          cachedEvents = data.events || [];
          renderEvents();
        }} catch (e) {{
          /* silent */
        }}
      }}

      function renderEvents() {{
        const svc = serviceFilter.value;
        const sev = severityFilter.value;
        const filtered = cachedEvents.filter(function(e) {{
          return (!svc || e.source === svc) && (!sev || e.severity === sev);
        }});
        logsTable.innerHTML = filtered.map(function(e) {{
          const details = e.details ? JSON.stringify(e.details) : '';
          return '<tr><td>' + e.created_at + '</td><td>' + e.source +
            '</td><td>' + e.severity + '</td><td>' + e.message +
            '</td><td><code>' + details + '</code></td></tr>';
        }}).join('');
      }}

      serviceFilter.addEventListener('change', renderEvents);
      severityFilter.addEventListener('change', renderEvents);
      loadEvents();

      autoRefresh.addEventListener('change', function() {{
        if (autoRefresh.checked) {{
          interval = setInterval(loadEvents, 5000);
        }} else if (interval) {{
          clearInterval(interval);
          interval = null;
        }}
      }});
    }}

    /* Network page: staged Wi-Fi connection polling */
    const wifiConnectForm = document.querySelector('form[data-endpoint="/api/network/wifi/connect"]');
    if (wifiConnectForm) {{
      const stagedStatus = document.getElementById('wifi-staged-status');
      let pollInterval = null;
      let pollTimeout = null;

      wifiConnectForm.addEventListener('submit', function() {{
        setTimeout(startWifiPolling, 500);
      }});

      function startWifiPolling() {{
        if (pollInterval) clearInterval(pollInterval);
        if (pollTimeout) clearTimeout(pollTimeout);
        if (stagedStatus) stagedStatus.textContent = 'Connecting...';

        pollInterval = setInterval(async function() {{
          try {{
            const resp = await fetch('/api/network');
            const data = await resp.json();
            const state = data.policy && data.policy.state;

            if (state === 'online_wifi') {{
              stopWifiPolling();
              if (stagedStatus) {{
                stagedStatus.innerHTML = 'Connected! <button id="wifi-confirm-btn">Confirm</button>';
                document.getElementById('wifi-confirm-btn').addEventListener('click', async function() {{
                  try {{
                    const d = await submitMutation('/api/network/wifi/confirm', {{}});
                    stagedStatus.textContent = d.message || 'Confirmed';
                  }} catch (e) {{ stagedStatus.textContent = e.message; }}
                }});
              }}
            }} else if (state === 'wifi_failed_recovery_hotspot') {{
              stopWifiPolling();
              if (stagedStatus) {{
                stagedStatus.innerHTML = 'Connection failed. <button id="wifi-fail-btn">Retry</button>';
                document.getElementById('wifi-fail-btn').addEventListener('click', async function() {{
                  try {{
                    const d = await submitMutation('/api/network/wifi/fail', {{}});
                    stagedStatus.textContent = d.message || 'Failed';
                  }} catch (e) {{ stagedStatus.textContent = e.message; }}
                }});
              }}
            }}
          }} catch (e) {{ /* silent */ }}
        }}, 3000);

        pollTimeout = setTimeout(function() {{
          stopWifiPolling();
          if (stagedStatus) stagedStatus.textContent = 'Connection timed out';
        }}, 60000);
      }}

      function stopWifiPolling() {{
        if (pollInterval) {{ clearInterval(pollInterval); pollInterval = null; }}
        if (pollTimeout) {{ clearTimeout(pollTimeout); pollTimeout = null; }}
      }}
    }}
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Page renderers
# ---------------------------------------------------------------------------


def _render_overview_page(snapshot) -> str:
    summary = snapshot.summary
    system = snapshot.system
    network = snapshot.network
    display = snapshot.display

    status_cards = "\n".join(
        _stat_card(label, value)
        for label, value in (
            ("Internet", summary["internet"]),
            ("Access", summary["access"]),
            ("Address", summary["address"] or "unassigned"),
            ("Hotspot", summary["hotspot"]),
            ("Core", summary["core"]),
            ("Display", summary["display"]),
        )
    )

    enabled_count = sum(1 for p in snapshot.pages if p["enabled"])

    return f"""
      <div class="grid">{status_cards}</div>
      <div class="content">
        <div>
          <section>
            <h2>Service Health</h2>
            <table>
              <tr><th>Core</th><td>{_esc(summary['core'])}</td></tr>
              <tr><th>Display</th><td>{_esc(summary['display'])}</td></tr>
              <tr><th>Admin</th><td>running</td></tr>
            </table>
          </section>
          <section>
            <h2>Network Summary</h2>
            <table>
              <tr><th>Wi-Fi</th><td>{_yes(network['wifi_connected'])} {_esc(network.get('wifi_ssid') or '')}</td></tr>
              <tr><th>Ethernet</th><td>{_yes(network['ethernet_connected'])}</td></tr>
              <tr><th>Hotspot</th><td>{_esc(summary['hotspot'])}</td></tr>
            </table>
          </section>
          <section>
            <h2>Quick Actions</h2>
            <div class="quick-actions">
              <a href="/network">Open Network</a>
              <a href="/dashboard" class="secondary-link">Open Dashboard</a>
            </div>
          </section>
        </div>
        <div>
          <section>
            <h2>Dashboard Summary</h2>
            <table>
              <tr><th>Active Page</th><td>{_esc(display.get('active_page_id') or '')}</td></tr>
              <tr><th>Enabled Pages</th><td>{enabled_count}</td></tr>
              <tr><th>Last Action</th><td>{_esc(display.get('last_action') or '')}</td></tr>
            </table>
          </section>
          <section>
            <h2>System Summary</h2>
            <table>
              <tr><th>Uptime</th><td>{system['uptime_seconds']:.0f}s</td></tr>
              <tr><th>CPU</th><td>{system['cpu_average_percent']:.0f}% avg</td></tr>
              <tr><th>Memory</th><td>{system['memory_percent']:.0f}%</td></tr>
            </table>
          </section>
        </div>
      </div>
    """


def _render_network_page(snapshot) -> str:
    network = snapshot.network
    policy = snapshot.network_policy
    summary = snapshot.summary
    recovery = snapshot.recovery

    staged_ssid = recovery.get("staged_wifi_ssid")
    staged_confirmed = recovery.get("staged_wifi_confirmed", False)
    wifi_retry_count = recovery.get("wifi_retry_count", 0)
    if staged_ssid:
        staged_label = (
            f"Confirmed: {_esc(staged_ssid)}" if staged_confirmed else f"Pending: {_esc(staged_ssid)}"
        )
    else:
        staged_label = "None"

    status_cards = "\n".join(
        _stat_card(label, value)
        for label, value in (
            ("Internet", summary["internet"]),
            ("Access", summary["access"]),
            ("Address", summary["address"] or "unassigned"),
            ("Hotspot", summary["hotspot"]),
        )
    )

    return f"""
      <div class="grid">{status_cards}</div>
      <div class="content">
        <div>
          <section>
            <h2>Network</h2>
            <table>
              <tr><th>Connection</th><td>{_esc(network['connection_type'])}</td></tr>
              <tr><th>Wi-Fi</th><td>{_yes(network['wifi_connected'])} {_esc(network.get('wifi_ssid') or '')}</td></tr>
              <tr><th>Ethernet</th><td>{_yes(network['ethernet_connected'])}</td></tr>
              <tr><th>Interfaces</th><td>{_esc(', '.join(network['active_interfaces']) or 'none')}</td></tr>
              <tr><th>Policy</th><td><code>{_esc(policy['state'])}</code></td></tr>
              <tr><th>Next Wi-Fi Action</th><td>{_esc(policy['wifi_action'])}</td></tr>
            </table>
            <div class="action-grid">
              <form data-endpoint="/api/network/wifi/scan">
                <button type="submit">Scan Wi-Fi</button>
              </form>
              <form data-endpoint="/api/network/wifi/connect">
                <label for="wifi-ssid">SSID</label>
                <input id="wifi-ssid" name="ssid" autocomplete="off">
                <label for="wifi-password">Password</label>
                <input id="wifi-password" name="password" type="password" autocomplete="new-password">
                <button type="submit">Connect Wi-Fi</button>
              </form>
              <form data-endpoint="/api/network/hotspot/enable">
                <label for="hotspot-mode">Mode</label>
                <select id="hotspot-mode" name="mode">
                  <option value="visible">Visible</option>
                  <option value="hidden">Hidden</option>
                </select>
                <button type="submit">Enable Hotspot</button>
              </form>
              <form data-endpoint="/api/network/hotspot/disable" data-confirm="Disable hotspot?">
                <button type="submit" class="secondary">Disable Hotspot</button>
              </form>
            </div>
          </section>
        </div>
        <div>
          <section>
            <h2>Recovery</h2>
            <table>
              <tr><th>Policy State</th><td><code>{_esc(policy['state'])}</code></td></tr>
              <tr><th>Hotspot Mode</th><td>{_esc(policy['hotspot_mode'])}</td></tr>
              <tr><th>Wi-Fi Action</th><td>{_esc(policy['wifi_action'])}</td></tr>
              <tr><th>Staged Wi-Fi</th><td>{staged_label}</td></tr>
              <tr><th>Retry Count</th><td>{wifi_retry_count}</td></tr>
            </table>
            <div id="wifi-staged-status" class="result" style="margin-top:8px"></div>
            <div class="actions">
              <form data-endpoint="/api/network/wifi/forget" data-confirm="Forget current Wi-Fi?">
                <button type="submit" class="secondary">Forget Wi-Fi</button>
              </form>
              <form data-endpoint="/api/network/policy/reconcile">
                <button type="submit">Reconcile Policy</button>
              </form>
              <form data-endpoint="/api/network/hotspot/rotate-password" data-confirm="Rotate hotspot password?">
                <button type="submit" class="secondary">Rotate Password</button>
              </form>
            </div>
          </section>
          <section>
            <h2>Mutation Safety</h2>
            <p class="notice">Network mutations now enter an allowlisted operation queue. Real NetworkManager changes remain disabled until the privileged helper and auth layers are wired.</p>
          </section>
        </div>
      </div>
    """


def _render_dashboard_page(snapshot) -> str:
    pages = "\n".join(_page_row(page) for page in snapshot.pages)
    dashboard = snapshot.dashboard
    display = snapshot.display
    enabled_count = sum(1 for p in snapshot.pages if p["enabled"])

    return f"""
      <div class="content">
        <div>
          <section>
            <h2>Preview</h2>
            <div class="preview">
              <img src="/api/dashboard/preview/overview.png" alt="Overview dashboard preview">
            </div>
          </section>
          <section>
            <h2>Dashboard Pages</h2>
            <table>
              <tr><th>Page</th><th>Enabled</th><th>Healthy</th><th>Last Error</th><th>Action</th></tr>
              {pages}
            </table>
          </section>
        </div>
        <div>
          <section>
            <h2>Rotation</h2>
            <table>
              <tr><th>Current Page</th><td>{_esc(dashboard.get('active_page_id') or '')}</td></tr>
              <tr><th>Next Rotation</th><td>{_esc(dashboard.get('next_rotation_at') or 'n/a')}</td></tr>
              <tr><th>Interval</th><td>{dashboard.get('rotation_interval_seconds', 0)}s</td></tr>
              <tr><th>Enabled Pages</th><td>{enabled_count}</td></tr>
            </table>
          </section>
          <section>
            <h2>Display Telemetry</h2>
            <table>
              <tr><th>Healthy</th><td>{_yes(display['healthy'])}</td></tr>
              <tr><th>Active Page</th><td>{_esc(display.get('active_page_id') or '')}</td></tr>
              <tr><th>Last Action</th><td>{_esc(display.get('last_action') or '')}</td></tr>
              <tr><th>Last Reason</th><td>{_esc(display.get('last_reason') or '')}</td></tr>
              <tr><th>Queue</th><td>{display['pending_frames']} pending</td></tr>
              <tr><th>Full Refreshes</th><td>{display.get('full_refreshes', 0)}</td></tr>
              <tr><th>Partial Refreshes</th><td>{display.get('partial_refreshes', 0)}</td></tr>
              <tr><th>Skipped</th><td>{display.get('skipped_refreshes', 0)}</td></tr>
            </table>
            <div class="actions" style="margin-top:10px">
              <button type="button" data-endpoint="/api/dashboard/refresh">Refresh Display Now</button>
            </div>
          </section>
        </div>
      </div>
    """


def _render_system_page(snapshot) -> str:
    system = snapshot.system
    core = snapshot.core
    display = snapshot.display

    return f"""
      <div class="content">
        <div>
          <section>
            <h2>System Pressure</h2>
            <table>
              <tr><th>CPU</th><td>{system['cpu_average_percent']:.0f}% avg / {system['cpu_peak_percent']:.0f}% peak</td></tr>
              <tr><th>Memory</th><td>{system['memory_percent']:.0f}% ({system['memory_used_gb']:.1f}/{system['memory_total_gb']:.1f} GB)</td></tr>
              <tr><th>Uptime</th><td>{system['uptime_seconds']:.0f}s</td></tr>
            </table>
          </section>
          <section>
            <h2>Process Health</h2>
            <table>
              <tr><th>Core</th><td>{'healthy' if core.get('healthy') else 'unhealthy'}</td></tr>
              <tr><th>Display</th><td>{'healthy' if display['healthy'] else 'unhealthy'}</td></tr>
              <tr><th>Admin</th><td>running</td></tr>
            </table>
          </section>
        </div>
        <div>
          <section>
            <h2>Restart Services</h2>
            <p class="notice">Restarting a service will briefly interrupt its operation. Confirm before proceeding.</p>
            <div class="restart-grid">
              <form data-endpoint="/api/system/restart/core" data-confirm="Restart core service?">
                <button type="submit">Restart Core</button>
              </form>
              <form data-endpoint="/api/system/restart/display" data-confirm="Restart display service?">
                <button type="submit">Restart Display</button>
              </form>
              <form data-endpoint="/api/system/restart/admin" data-confirm="Restart admin service? This will end your current session.">
                <button type="submit" class="secondary">Restart Admin</button>
              </form>
            </div>
          </section>
        </div>
      </div>
    """


def _render_logs_page(snapshot) -> str:
    return """
      <section>
        <h2>Event Stream</h2>
        <div class="filter-bar">
          <label for="log-service">Service</label>
          <select id="log-service">
            <option value="">All</option>
            <option value="network">Network</option>
            <option value="dashboard">Dashboard</option>
            <option value="core">Core</option>
            <option value="display">Display</option>
            <option value="admin">Admin</option>
          </select>
          <label for="log-severity">Severity</label>
          <select id="log-severity">
            <option value="">All</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
          <label>
            <input id="log-auto-refresh" type="checkbox"> Auto-refresh
          </label>
        </div>
        <table>
          <tr><th>Timestamp</th><th>Source</th><th>Severity</th><th>Message</th><th>Details</th></tr>
          <tbody id="logs-table"></tbody>
        </table>
      </section>
    """


def _render_settings_page(snapshot) -> str:
    dashboard = snapshot.dashboard
    policy = snapshot.network_policy

    return f"""
      <div class="content">
        <div>
          <section>
            <h2>Settings</h2>
            <form class="settings-form" data-endpoint="/api/settings">
              <label for="settings-hostname">Hostname</label>
              <input id="settings-hostname" value="{_esc(snapshot.hostname)}" readonly class="readonly">

              <label for="settings-auth">Auth Token</label>
              <input id="settings-auth" value="configured (enter in header)" readonly class="readonly">

              <label for="settings-hotspot-mode">Hotspot Mode</label>
              <select id="settings-hotspot-mode" name="hotspot_mode">
                <option value="off"{' selected' if policy.get('hotspot_mode') == 'off' else ''}>Off</option>
                <option value="visible"{' selected' if policy.get('hotspot_mode') == 'visible' else ''}>Visible</option>
                <option value="hidden"{' selected' if policy.get('hotspot_mode') == 'hidden' else ''}>Hidden</option>
              </select>

              <label for="settings-rotation-interval">Rotation Interval (seconds)</label>
              <input id="settings-rotation-interval" name="rotation_interval_seconds"
                     type="number" min="60" step="30"
                     value="{dashboard.get('rotation_interval_seconds', 300)}">

              <div class="actions">
                <button type="submit">Save Settings</button>
              </div>
            </form>
          </section>
        </div>
        <div>
          <section>
            <h2>Current Configuration</h2>
            <table>
              <tr><th>Hostname</th><td>{_esc(snapshot.hostname)}</td></tr>
              <tr><th>Hotspot Mode</th><td>{_esc(policy.get('hotspot_mode', 'off'))}</td></tr>
              <tr><th>Rotation Interval</th><td>{dashboard.get('rotation_interval_seconds', 300)}s</td></tr>
            </table>
          </section>
        </div>
      </div>
    """


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def _nav_item(section: dict, active_route: str) -> str:
    route = section["route"]
    active = ' active' if route == active_route else ""
    return f'<a class="nav-item{active}" href="{_esc(route)}">{_esc(section["label"])}</a>'


def _stat_card(label: str, value: str) -> str:
    return f'<div class="card"><div class="label">{_esc(label)}</div><div class="value">{_esc(value)}</div></div>'


def _page_row(page: dict) -> str:
    page_id = str(page["page_id"])
    action = "disable" if page["enabled"] else "enable"
    label = "Disable" if page["enabled"] else "Enable"
    confirm = ' data-confirm="Disable page?"' if page["enabled"] else ""
    endpoint = f"/api/dashboard/pages/{_esc(page_id)}/{action}"
    return (
        f"<tr><td>{_esc(page_id)}</td><td>{_yes(page['enabled'])}</td>"
        f"<td>{_yes(page['healthy'])}</td><td>{_esc(page.get('last_error') or '')}</td>"
        f'<td><button type="button" data-endpoint="{endpoint}"{confirm}>{label}</button></td></tr>'
    )


def _title_for_route(sections: list[dict], route: str) -> str:
    for section in sections:
        if section["route"] == route:
            return section["label"]
    return "Overview"


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


_NETWORK_POST_ROUTES = {
    "/api/network/wifi/scan": "wifi_scan",
    "/api/network/wifi/connect": "wifi_connect",
    "/api/network/wifi/forget": "wifi_forget",
    "/api/network/hotspot/enable": "hotspot_enable",
    "/api/network/hotspot/disable": "hotspot_disable",
    "/api/network/hotspot/rotate-password": "hotspot_rotate_password",
    "/api/network/policy/reconcile": "policy_reconcile",
}


def _dashboard_page_mutation(route: str) -> tuple[str, bool] | None:
    prefix = "/api/dashboard/pages/"
    if not route.startswith(prefix):
        return None
    remainder = route[len(prefix):]
    page_id, _, action = remainder.rpartition("/")
    if not page_id or action not in {"enable", "disable"}:
        return None
    return page_id, action == "enable"
