from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_all_service_templates_render_without_placeholders() -> None:
    replacements = {
        "__SERVICE_USER__": "inkpi",
        "__SERVICE_GROUP__": "inkpi",
        "__SERVICE_HOME__": "/home/inkpi",
        "__SERVICE_PATH__": "/usr/local/bin:/usr/bin:/bin",
        "__WORKDIR__": "/opt/inkpi/backend",
        "__FRONTEND_DIST__": "/opt/inkpi/frontend/dist",
        "__BACKEND_BIN__": "/opt/inkpi/backend/.venv/bin",
    }

    for template in (ROOT / "deploy/systemd").glob("*.service"):
        rendered = template.read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        assert re.search(r"__[A-Z0-9_]+__", rendered) is None, template
        assert "WorkingDirectory=/opt/inkpi/backend" in rendered
        assert "ExecStart=/opt/inkpi/backend/.venv/bin/inkpi-" in rendered


def test_pi_units_preserve_process_boundaries() -> None:
    api = (ROOT / "deploy/systemd/inkpi-api.service").read_text(encoding="utf-8")
    helper = (ROOT / "deploy/systemd/inkpi-network-helper.service").read_text(encoding="utf-8")
    display = (ROOT / "deploy/systemd/inkpi-display.service").read_text(encoding="utf-8")

    assert "User=__SERVICE_USER__" in api
    assert "ExecStart=__BACKEND_BIN__/inkpi-api" in api
    assert "--web-dist __FRONTEND_DIST__" in api
    assert "Wants=network-online.target inkpi-network-helper.service" in api
    assert "Requires=inkpi-network-helper.service" not in api
    assert "User=root" in helper
    assert "ExecStart=__BACKEND_BIN__/inkpi-network-helper" in helper
    assert "RuntimeDirectoryMode=0770" in helper
    assert "ExecStart=__BACKEND_BIN__/inkpi-display --api-url http://127.0.0.1:8080" in display
    assert "Requires=inkpi-api.service" in display


def test_pi_installer_prepares_dependencies_and_replaces_legacy_runtime() -> None:
    installer = (ROOT / "deploy/install_pi.sh").read_text(encoding="utf-8")

    assert 'SERVICE_USER="${INKPI_SERVICE_USER:-${SUDO_USER:-}}"' in installer
    assert '"${SERVICE_USER}" == "root"' in installer
    assert 'sync --project "${BACKEND_DIR}" --extra rpi' in installer
    assert "playwright install-deps chromium" in installer
    assert "playwright install chromium" in installer
    assert 'install --frozen-lockfile && "$2" run build' in installer
    assert "install_unit inkpi-display.service inkpi-display.service" in installer
    assert "disable --now eink-dashboard.service inkpi-core.service inkpi-admin.service" in installer
    assert "curl -fsS http://127.0.0.1:8080/api/health" in installer
    assert "systemctl is-active --quiet inkpi-display.service" in installer


def test_only_current_service_templates_remain() -> None:
    names = {path.name for path in (ROOT / "deploy/systemd").glob("*.service")}
    assert names == {
        "inkpi-api.service",
        "inkpi-display.service",
        "inkpi-host-agent.service",
        "inkpi-network-helper.service",
    }


def test_pi_uninstaller_preserves_data_and_removes_only_units() -> None:
    uninstaller = (ROOT / "deploy/uninstall_pi.sh").read_text(encoding="utf-8")

    assert "systemctl disable --now" in uninstaller
    assert 'rm -f "/etc/systemd/system/${unit}"' in uninstaller
    assert "Application data, environment files, and backups were preserved" in uninstaller
