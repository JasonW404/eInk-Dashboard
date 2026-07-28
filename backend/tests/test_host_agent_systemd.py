from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_host_agent_systemd_template_keeps_secrets_in_environment_file() -> None:
    service = (ROOT / "deploy/systemd/inkpi-host-agent.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=/etc/inkpi/host-agent.env" in service
    assert "ExecStart=__BACKEND_BIN__/inkpi-host-agent" in service
    assert "Restart=always" in service
    assert "NoNewPrivileges=true" in service


def test_host_agent_uninstaller_preserves_credentials() -> None:
    uninstaller = (ROOT / "deploy/uninstall_cloud.sh").read_text(encoding="utf-8")

    assert "systemctl disable --now" in uninstaller
    assert 'rm -f "/etc/systemd/system/${unit}"' in uninstaller
    assert "credentials, environment files, and backups were preserved" in uninstaller


def test_deployment_environment_templates_exist_without_real_secrets() -> None:
    cloud = (ROOT / "deploy/env/cloud.env.example").read_text(encoding="utf-8")
    display = (ROOT / "deploy/env/pi-display.env.example").read_text(encoding="utf-8")
    host = (ROOT / "deploy/env/host-agent.env.example").read_text(encoding="utf-8")

    assert "INKPI_ADMIN_TOKEN=replace-with" in cloud
    assert "INKPI_AGENT_ENROLLMENT_TOKEN=replace-with" in cloud
    assert "INKPI_DISPLAY_TOKEN=replace-with" in display
    assert "INKPI_API_URL=http://inkpi.local:8080" in host
    assert "EINK_GITHUB_API_KEY=replace-with" in host
