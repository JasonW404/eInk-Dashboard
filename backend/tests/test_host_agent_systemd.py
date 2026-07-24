from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_host_agent_systemd_template_keeps_secrets_in_environment_file() -> None:
    service = (ROOT / "deploy/systemd/inkpi-host-agent.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=__SERVICE_HOME__/.config/inkpi/host-agent.env" in service
    assert "ExecStart=__BACKEND_BIN__/inkpi-host-agent" in service
    assert "Restart=always" in service
    assert "NoNewPrivileges=true" in service


def test_host_agent_installer_prepares_environment_and_enables_service() -> None:
    installer = (ROOT / "deploy/install_host_agent.sh").read_text(encoding="utf-8")
    assert "host-agent.env" in installer
    assert 'SERVICE_USER="${INKPI_SERVICE_USER:-${SUDO_USER:-}}"' in installer
    assert 'sync --project "${BACKEND_DIR}"' in installer
    assert "INKPI_API_URL is required" in installer
    assert "set INKPI_AGENT_ENROLLMENT_TOKEN for first registration" in installer
    assert 'systemctl enable --now "${SERVICE_NAME}"' in installer
    assert 'systemctl is-active --quiet "${SERVICE_NAME}"' in installer


def test_host_agent_uninstaller_preserves_credentials() -> None:
    uninstaller = (ROOT / "deploy/uninstall_host_agent.sh").read_text(encoding="utf-8")

    assert "systemctl disable --now" in uninstaller
    assert 'rm -f "/etc/systemd/system/${unit}"' in uninstaller
    assert "Credentials, environment files, and backups were preserved" in uninstaller


def test_deployment_environment_templates_exist_without_real_secrets() -> None:
    api = (ROOT / "deploy/env/api.env.example").read_text(encoding="utf-8")
    host = (ROOT / "deploy/env/host-agent.env.example").read_text(encoding="utf-8")

    assert "INKPI_ADMIN_TOKEN=replace-with" in api
    assert "INKPI_AGENT_ENROLLMENT_TOKEN=replace-with" in api
    assert "INKPI_API_URL=http://inkpi.local:8080" in host
    assert "EINK_GITHUB_API_KEY=replace-with" in host
