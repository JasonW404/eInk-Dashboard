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


def test_cloud_and_pi_units_preserve_process_boundaries() -> None:
    cloud = (ROOT / "deploy/systemd/inkpi-cloud.service").read_text(encoding="utf-8")
    display = (ROOT / "deploy/systemd/inkpi-display.service").read_text(encoding="utf-8")

    assert "User=__SERVICE_USER__" in cloud
    assert "ExecStart=__BACKEND_BIN__/inkpi-api" in cloud
    assert "--web-dist __FRONTEND_DIST__" in cloud
    assert "inkpi-network-helper" not in cloud
    assert "ExecStart=__BACKEND_BIN__/inkpi-display" in display
    assert "pi-display.env" in display
    assert "inkpi-api.service" not in display


def test_binary_bundle_installers_require_no_language_toolchain() -> None:
    cloud = (ROOT / "packaging/install_cloud_bundle.sh").read_text(encoding="utf-8")
    display = (ROOT / "packaging/install_display_bundle.sh").read_text(encoding="utf-8")

    for installer in (cloud, display):
        assert "uv sync" not in installer
        assert "python3" not in installer
        assert "bun install" not in installer
        assert "node " not in installer
        assert "BUNDLE_ARCH" in installer
        assert "/opt/inkpi/" in installer
        assert 'SERVICE_USER="inkpi"' in installer
        assert "useradd --system --user-group" in installer
        assert "INKPI_SERVICE_USER" not in installer
        assert '== "root:root"' in installer
        assert "--reconfigure" in installer
        assert "read -r -s -p" in installer
        assert "interactive input is required" in installer
    assert "chromium" in cloud
    assert "inkpi-cloud.service" in cloud
    assert "--enable-host-agent" in cloud
    assert "inkpi-host-agent.service" in cloud
    assert "GitHub API token" in cloud
    assert "inkpi-display.service" in display


def test_release_builds_both_roles_on_native_amd64_and_arm64() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "runner: ubuntu-22.04" in workflow
    assert "runner: ubuntu-22.04-arm" in workflow
    assert "arch: amd64" in workflow
    assert "arch: arm64" in workflow
    assert "inkpi-cloud-${VERSION}-linux-${ARCH}" in workflow
    assert "inkpi-display-${VERSION}-linux-${ARCH}" in workflow
    assert "build/standalone/inkpi-host-agent" in workflow
    assert "inkpi-host-agent.service" in workflow
    assert "packaging/build_binaries.sh" in workflow
    assert "SHA256SUMS" in workflow


def test_only_current_service_templates_remain() -> None:
    names = {path.name for path in (ROOT / "deploy/systemd").glob("*.service")}
    assert names == {
        "inkpi-cloud.service",
        "inkpi-display.service",
        "inkpi-host-agent.service",
    }


def test_pi_uninstaller_preserves_data_and_removes_only_display_unit() -> None:
    uninstaller = (ROOT / "deploy/uninstall_pi.sh").read_text(encoding="utf-8")

    assert "units=(inkpi-display.service)" in uninstaller
    assert "systemctl disable --now" in uninstaller
    assert 'rm -f "/etc/systemd/system/${unit}"' in uninstaller
    assert "Configuration files, data, and backups were preserved" in uninstaller
