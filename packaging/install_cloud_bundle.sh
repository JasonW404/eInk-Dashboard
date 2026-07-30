#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENABLE_HOST_AGENT=false
HOST_AGENT_API_URL="http://127.0.0.1:8080"
HOST_AGENT_NAME="$(hostname)"
RECONFIGURE=false

fail() {
  echo "InkPi cloud binary install failed: $*" >&2
  exit 1
}

usage() {
  echo "Usage: sudo ./install.sh [--reconfigure] [--enable-host-agent] [--host-agent-api-url URL] [--host-agent-name NAME]"
}

prompt_secret() {
  local variable_name="$1"
  local prompt="$2"
  local value=""
  while [[ -z "${value}" || "${value}" == *[[:space:]]* ]]; do
    read -r -s -p "${prompt}: " value
    echo >&2
    if [[ -z "${value}" || "${value}" == *[[:space:]]* ]]; then
      echo "A non-empty value without whitespace is required." >&2
    fi
  done
  printf -v "${variable_name}" '%s' "${value}"
}

prompt_optional_secret() {
  local variable_name="$1"
  local prompt="$2"
  local value=""
  read -r -s -p "${prompt} (optional, press Enter to skip): " value
  echo >&2
  [[ "${value}" != *[[:space:]]* ]] || fail "${prompt} must not contain whitespace"
  printf -v "${variable_name}" '%s' "${value}"
}

while (($#)); do
  case "$1" in
    --enable-host-agent)
      ENABLE_HOST_AGENT=true
      shift
      ;;
    --reconfigure)
      RECONFIGURE=true
      shift
      ;;
    --host-agent-api-url)
      (($# >= 2)) || fail "--host-agent-api-url requires a value"
      HOST_AGENT_API_URL="$2"
      shift 2
      ;;
    --host-agent-name)
      (($# >= 2)) || fail "--host-agent-name requires a value"
      HOST_AGENT_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ $(uname -s) == "Linux" ]] || fail "this installer requires Linux"
[[ ${EUID} -eq 0 ]] || fail "run with: sudo ./install.sh"
[[ -f "${SCRIPT_DIR}/VERSION" && -f "${SCRIPT_DIR}/ARCH" ]] || fail "incomplete release bundle"
[[ -x "${SCRIPT_DIR}/inkpi-cloud/inkpi-api" ]] || fail "cloud executable is missing"
[[ -x "${SCRIPT_DIR}/inkpi-host-agent/inkpi-host-agent" ]] || fail "HostAgent executable is missing"
[[ -f "${SCRIPT_DIR}/web/index.html" && -f "${SCRIPT_DIR}/web/eink.html" ]] || fail "prebuilt Web assets are missing"
[[ "${HOST_AGENT_API_URL}" =~ ^https?://[^[:space:]]+$ ]] \
  || fail "HostAgent API URL must be an http(s) URL without whitespace"
[[ "${HOST_AGENT_NAME}" =~ ^[A-Za-z0-9._-]+$ ]] \
  || fail "HostAgent name may contain only letters, digits, dot, underscore, and hyphen"

case "$(uname -m)" in
  x86_64|amd64) HOST_ARCH="amd64" ;;
  aarch64|arm64) HOST_ARCH="arm64" ;;
  *) fail "unsupported architecture: $(uname -m)" ;;
esac
BUNDLE_ARCH="$(tr -d '[:space:]' < "${SCRIPT_DIR}/ARCH")"
[[ "${HOST_ARCH}" == "${BUNDLE_ARCH}" ]] || fail "bundle is ${BUNDLE_ARCH}, host is ${HOST_ARCH}"
VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/VERSION")"

SERVICE_USER="inkpi"
SERVICE_HOME="/var/lib/inkpi"
if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --user-group --home-dir "${SERVICE_HOME}" --create-home \
    --shell /usr/sbin/nologin "${SERVICE_USER}"
fi
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
[[ "$(getent passwd "${SERVICE_USER}" | cut -d: -f6)" == "${SERVICE_HOME}" ]] \
  || fail "existing inkpi account must use ${SERVICE_HOME} as its home"

CONFIG_DIR="/etc/inkpi"
CLOUD_ENV="${CONFIG_DIR}/cloud.env"
install -d -o root -g root -m 0700 "${CONFIG_DIR}"
if [[ ! -f "${CLOUD_ENV}" || "${RECONFIGURE}" == true ]]; then
  [[ -t 0 ]] || fail "interactive input is required; run from a terminal or pre-create ${CLOUD_ENV}"
  echo "Configure InkPi Cloud. Secret values are hidden while typing."
  prompt_secret admin_token "Admin token"
  prompt_secret display_token "Display token shared with the Pi"
  prompt_secret network_token "Network token shared with the Pi network service"
  prompt_secret enrollment_token "HostAgent enrollment token"
  config_temporary="$(mktemp)"
  {
    printf 'INKPI_ADMIN_TOKEN=%s\n' "${admin_token}"
    printf 'INKPI_DISPLAY_TOKEN=%s\n' "${display_token}"
    printf 'INKPI_NETWORK_TOKEN=%s\n' "${network_token}"
    printf 'INKPI_AGENT_ENROLLMENT_TOKEN=%s\n' "${enrollment_token}"
    printf 'INKPI_DATABASE_URL=sqlite+pysqlite:////var/lib/inkpi/inkpi.db\n'
    printf 'INKPI_UPLOAD_DIR=/var/lib/inkpi/pages\n'
    printf 'INKPI_CHROMIUM_EXECUTABLE=/usr/bin/chromium\n'
  } > "${config_temporary}"
  install -o root -g root -m 0600 "${config_temporary}" "${CLOUD_ENV}"
  rm -f "${config_temporary}"
  unset admin_token display_token network_token enrollment_token
fi
[[ $(stat -c '%U:%G' "${CLOUD_ENV}") == "root:root" ]] || fail "${CLOUD_ENV} must be owned by root:root"
[[ -z "$(find "${CLOUD_ENV}" -perm /077 -print -quit)" ]] || fail "${CLOUD_ENV} must use mode 0600"
grep -Eq '^[[:space:]]*INKPI_ADMIN_TOKEN=.+$' "${CLOUD_ENV}" || fail "INKPI_ADMIN_TOKEN is required"
grep -Eq '^[[:space:]]*INKPI_DISPLAY_TOKEN=.+$' "${CLOUD_ENV}" || fail "INKPI_DISPLAY_TOKEN is required"
grep -Eq '^[[:space:]]*INKPI_NETWORK_TOKEN=.+$' "${CLOUD_ENV}" || fail "INKPI_NETWORK_TOKEN is required"
grep -q 'replace-with-' "${CLOUD_ENV}" && fail "replace all placeholder tokens in ${CLOUD_ENV}"

if ! command -v chromium >/dev/null 2>&1; then
  command -v apt-get >/dev/null 2>&1 || fail "Chromium is required; install it and rerun"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y chromium ca-certificates curl
fi

RELEASE_DIR="/opt/inkpi/cloud/${VERSION}-${HOST_ARCH}"
install -d -m 0755 "${RELEASE_DIR}"
cp -a "${SCRIPT_DIR}/inkpi-cloud" "${RELEASE_DIR}/"
cp -a "${SCRIPT_DIR}/inkpi-host-agent" "${RELEASE_DIR}/"
cp -a "${SCRIPT_DIR}/web" "${RELEASE_DIR}/"
install -m 0644 "${SCRIPT_DIR}/VERSION" "${RELEASE_DIR}/VERSION"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 /var/lib/inkpi /var/lib/inkpi/pages
ln -sfn "${RELEASE_DIR}" /opt/inkpi/cloud/current

temporary="$(mktemp)"
trap 'rm -f "${temporary}"' EXIT
sed \
  -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
  -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
  -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
  -e "s|__SERVICE_PATH__|/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin|g" \
  -e "s|__WORKDIR__|/opt/inkpi/cloud/current|g" \
  -e "s|__FRONTEND_DIST__|/opt/inkpi/cloud/current/web|g" \
  -e "s|__BACKEND_BIN__|/opt/inkpi/cloud/current/inkpi-cloud|g" \
  "${SCRIPT_DIR}/systemd/inkpi-cloud.service" > "${temporary}"
if [[ -f /etc/systemd/system/inkpi-cloud.service ]]; then
  cp -a /etc/systemd/system/inkpi-cloud.service \
    "/etc/systemd/system/inkpi-cloud.service.bak.$(date +%Y%m%d%H%M%S)"
fi
install -m 0644 "${temporary}" /etc/systemd/system/inkpi-cloud.service

if [[ "${ENABLE_HOST_AGENT}" == true ]]; then
  enrollment_token="$(sed -n 's/^[[:space:]]*INKPI_AGENT_ENROLLMENT_TOKEN=//p' "${CLOUD_ENV}" | tail -1)"
  [[ -n "${enrollment_token}" ]] || fail "cloud configuration must contain INKPI_AGENT_ENROLLMENT_TOKEN"
  HOST_AGENT_ENV="${CONFIG_DIR}/host-agent.env"
  github_token=""
  if [[ -t 0 ]]; then
    prompt_optional_secret github_token "GitHub API token for private contribution data"
  fi
  if [[ -z "${github_token}" && -f "${HOST_AGENT_ENV}" ]]; then
    github_token="$(sed -n 's/^[[:space:]]*EINK_GITHUB_API_KEY=//p' "${HOST_AGENT_ENV}" | tail -1)"
  fi
  install -o root -g root -m 0600 /dev/null "${HOST_AGENT_ENV}"
  {
    printf 'INKPI_API_URL=%s\n' "${HOST_AGENT_API_URL}"
    printf 'INKPI_AGENT_NAME=%s\n' "${HOST_AGENT_NAME}"
    printf 'INKPI_AGENT_CREDENTIALS=/var/lib/inkpi/host-agent.json\n'
    printf 'INKPI_AGENT_ENROLLMENT_TOKEN=%s\n' "${enrollment_token}"
    if [[ -n "${github_token}" ]]; then
      printf 'EINK_GITHUB_API_KEY=%s\n' "${github_token}"
    fi
  } > "${HOST_AGENT_ENV}"
  unset github_token
  chown root:root "${HOST_AGENT_ENV}"
  chmod 0600 "${HOST_AGENT_ENV}"

  sed \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
    -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
    -e "s|__SERVICE_PATH__|/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin|g" \
    -e "s|__WORKDIR__|/opt/inkpi/cloud/current|g" \
    -e "s|__BACKEND_BIN__|/opt/inkpi/cloud/current/inkpi-host-agent|g" \
    "${SCRIPT_DIR}/systemd/inkpi-host-agent.service" > "${temporary}"
  if [[ -f /etc/systemd/system/inkpi-host-agent.service ]]; then
    cp -a /etc/systemd/system/inkpi-host-agent.service \
      "/etc/systemd/system/inkpi-host-agent.service.bak.$(date +%Y%m%d%H%M%S)"
  fi
  install -m 0644 "${temporary}" /etc/systemd/system/inkpi-host-agent.service
fi

systemd-analyze verify /etc/systemd/system/inkpi-cloud.service
if [[ "${ENABLE_HOST_AGENT}" == true ]]; then
  systemd-analyze verify /etc/systemd/system/inkpi-host-agent.service
fi
systemctl daemon-reload
systemctl enable --now inkpi-cloud.service
systemctl restart inkpi-cloud.service
for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://127.0.0.1:8080/api/health >/dev/null || fail "cloud health check failed"
if [[ "${ENABLE_HOST_AGENT}" == true ]]; then
  systemctl enable --now inkpi-host-agent.service
  systemctl restart inkpi-host-agent.service
  HOST_AGENT_CREDENTIALS="/var/lib/inkpi/host-agent.json"
  for _ in $(seq 1 30); do
    [[ -s "${HOST_AGENT_CREDENTIALS}" ]] && break
    sleep 1
  done
  [[ -s "${HOST_AGENT_CREDENTIALS}" ]] || fail "HostAgent enrollment did not produce credentials"
  sed -i '/^[[:space:]]*INKPI_AGENT_ENROLLMENT_TOKEN=/d' "${HOST_AGENT_ENV}"
  systemctl restart inkpi-host-agent.service
  sleep 2
  systemctl is-active --quiet inkpi-host-agent.service || fail "HostAgent service is not active"
fi
echo "InkPi cloud ${VERSION} (${HOST_ARCH}) installed without Python, uv, or Bun."
