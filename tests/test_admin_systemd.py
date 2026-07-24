from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_service_is_installed_with_core_and_display() -> None:
    installer = (ROOT / "scripts/systemd/install_inkpi_services.sh").read_text(encoding="utf-8")

    assert "inkpi-admin.service" in installer
    assert "systemctl enable inkpi-display.service inkpi-core.service inkpi-admin.service" in installer
    assert "systemctl start inkpi-admin.service" in installer


def test_admin_service_template_uses_packaged_entrypoint_and_core_socket() -> None:
    service = (ROOT / "scripts/systemd/inkpi-admin.service").read_text(encoding="utf-8")

    assert "Description=InkPi Local Admin Portal" in service
    assert "EnvironmentFile=-__SERVICE_HOME__/.config/inkpi/admin.env" in service
    assert "RuntimeDirectory=inkpi-admin" in service
    assert "run inkpi-admin --host 0.0.0.0 --port 8081 --core-socket /run/inkpi-core/core.sock" in service
