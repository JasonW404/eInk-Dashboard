#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECONFIGURE=false

fail() {
  echo "InkPi display binary install failed: $*" >&2
  exit 1
}

usage() {
  echo "Usage: sudo ./install.sh [--reconfigure]"
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

while (($#)); do
  case "$1" in
    --reconfigure)
      RECONFIGURE=true
      shift
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
[[ -x "${SCRIPT_DIR}/inkpi-display/inkpi-display" ]] || fail "display executable is missing"

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
DISPLAY_ENV="${CONFIG_DIR}/pi-display.env"
install -d -o root -g root -m 0700 "${CONFIG_DIR}"
if [[ ! -f "${DISPLAY_ENV}" || "${RECONFIGURE}" == true ]]; then
  [[ -t 0 ]] || fail "interactive input is required; run from a terminal or pre-create ${DISPLAY_ENV}"
  echo "Configure the InkPi display client. Secret values are hidden while typing."
  api_url=""
  while [[ ! "${api_url}" =~ ^https?://[^[:space:]]+$ ]]; do
    read -r -p "InkPi Cloud API URL: " api_url
    if [[ ! "${api_url}" =~ ^https?://[^[:space:]]+$ ]]; then
      echo "Enter a valid http(s) URL without whitespace." >&2
    fi
  done
  prompt_secret display_token "Display token from InkPi Cloud"
  config_temporary="$(mktemp)"
  {
    printf 'INKPI_API_URL=%s\n' "${api_url}"
    printf 'INKPI_DISPLAY_TOKEN=%s\n' "${display_token}"
    printf 'INKPI_DISPLAY_POLL_SECONDS=5\n'
    printf 'INKPI_DISPLAY_DEBOUNCE_SECONDS=1\n'
  } > "${config_temporary}"
  install -o root -g root -m 0600 "${config_temporary}" "${DISPLAY_ENV}"
  rm -f "${config_temporary}"
  unset api_url display_token
fi
[[ $(stat -c '%U:%G' "${DISPLAY_ENV}") == "root:root" ]] || fail "${DISPLAY_ENV} must be owned by root:root"
[[ -z "$(find "${DISPLAY_ENV}" -perm /077 -print -quit)" ]] || fail "${DISPLAY_ENV} must use mode 0600"
grep -Eq '^[[:space:]]*INKPI_API_URL=https?://.+$' "${DISPLAY_ENV}" || fail "INKPI_API_URL is required"
grep -Eq '^[[:space:]]*INKPI_DISPLAY_TOKEN=.+$' "${DISPLAY_ENV}" || fail "INKPI_DISPLAY_TOKEN is required"
grep -q 'replace-with-' "${DISPLAY_ENV}" && fail "replace the placeholder token in ${DISPLAY_ENV}"

for group in spi gpio; do
  if getent group "${group}" >/dev/null && ! id -nG "${SERVICE_USER}" | tr ' ' '\n' | grep -qx "${group}"; then
    usermod -a -G "${group}" "${SERVICE_USER}"
  fi
done

RELEASE_DIR="/opt/inkpi/display/${VERSION}-${HOST_ARCH}"
install -d -m 0755 "${RELEASE_DIR}"
cp -a "${SCRIPT_DIR}/inkpi-display" "${RELEASE_DIR}/"
install -m 0644 "${SCRIPT_DIR}/VERSION" "${RELEASE_DIR}/VERSION"
ln -sfn "${RELEASE_DIR}" /opt/inkpi/display/current

temporary="$(mktemp)"
trap 'rm -f "${temporary}"' EXIT
sed \
  -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
  -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
  -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
  -e "s|__SERVICE_PATH__|/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin|g" \
  -e "s|__WORKDIR__|/opt/inkpi/display/current|g" \
  -e "s|__BACKEND_BIN__|/opt/inkpi/display/current/inkpi-display|g" \
  "${SCRIPT_DIR}/systemd/inkpi-display.service" > "${temporary}"
if [[ -f /etc/systemd/system/inkpi-display.service ]]; then
  cp -a /etc/systemd/system/inkpi-display.service \
    "/etc/systemd/system/inkpi-display.service.bak.$(date +%Y%m%d%H%M%S)"
fi
install -m 0644 "${temporary}" /etc/systemd/system/inkpi-display.service

systemd-analyze verify /etc/systemd/system/inkpi-display.service
systemctl daemon-reload
systemctl enable --now inkpi-display.service
systemctl restart inkpi-display.service
sleep 2
systemctl is-active --quiet inkpi-display.service || fail "display service is not active"
echo "InkPi display ${VERSION} (${HOST_ARCH}) installed without Python or uv."
