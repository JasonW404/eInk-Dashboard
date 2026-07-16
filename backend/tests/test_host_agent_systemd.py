from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_host_agent_systemd_template_keeps_secrets_in_environment_file() -> None:
    service = (ROOT / "deploy/systemd/inkpi-host-agent.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=__SERVICE_HOME__/.config/inkpi/host-agent.env" in service
    assert "run inkpi-host-agent" in service
    assert "Restart=always" in service


def test_host_agent_installer_requires_environment_file_and_enables_service() -> None:
    installer = (ROOT / "deploy/install_host_agent.sh").read_text(encoding="utf-8")
    assert "host-agent.env" in installer
    assert 'systemctl enable --now "${SERVICE_NAME}"' in installer
    assert "chmod 600" not in installer
