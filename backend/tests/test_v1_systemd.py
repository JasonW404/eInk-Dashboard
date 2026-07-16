from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v1_api_and_display_units_preserve_process_boundaries() -> None:
    api = (ROOT / "deploy/systemd/inkpi-api.service").read_text(encoding="utf-8")
    helper = (ROOT / "deploy/systemd/inkpi-network-helper.service").read_text(encoding="utf-8")
    display = (ROOT / "deploy/systemd/inkpi-display.service").read_text(encoding="utf-8")

    assert "User=__SERVICE_USER__" in api
    assert "run inkpi-api" in api
    assert "--web-dist __FRONTEND_DIST__" in api
    assert "User=root" in helper
    assert "run inkpi-network-helper" in helper
    assert "RuntimeDirectoryMode=0770" in helper
    assert "run inkpi-display --api-url http://127.0.0.1:8080" in display
    assert "Requires=inkpi-api.service" in display


def test_v1_installer_replaces_legacy_runtime_without_two_panel_owners() -> None:
    installer = (ROOT / "deploy/install_pi.sh").read_text(encoding="utf-8")

    assert "install_unit inkpi-display.service inkpi-display.service" in installer
    assert "disable --now eink-dashboard.service inkpi-core.service inkpi-admin.service" in installer
    assert "systemctl enable inkpi-network-helper.service inkpi-api.service inkpi-display.service" in installer


def test_only_v1_service_templates_remain() -> None:
    names = {path.name for path in (ROOT / "deploy/systemd").glob("*.service")}
    assert names == {
        "inkpi-api.service",
        "inkpi-display.service",
        "inkpi-host-agent.service",
        "inkpi-network-helper.service",
    }
