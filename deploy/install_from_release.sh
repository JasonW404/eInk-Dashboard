#!/usr/bin/env bash
set -euo pipefail

# InkPi Release Installer
# Installs InkPi from a pre-built release tarball on a Raspberry Pi.
# Requires: Linux, ARM64, root (sudo), Python 3.12+
# No uv, bun, or source repository needed on the target.
#
# Usage: sudo bash install.sh [--install-dir /opt/inkpi]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INKPI_INSTALL_DIR:-/opt/inkpi}"

fail() { echo "InkPi install failed: $*" >&2; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    *) fail "unknown option: $1" ;;
  esac
done

# --- Validation ---
[[ $(uname -s) == "Linux" ]] || fail "this installer must run on Linux"
[[ ${EUID} -ne 0 ]] && fail "run with: sudo bash install.sh"

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' \
  || fail "Python 3.12+ required; found $(python3 --version 2>&1)"

case "$(uname -m)" in
  aarch64|arm64) ;;
  *) fail "requires 64-bit ARM OS; found $(uname -m)" ;;
esac

SERVICE_USER="${INKPI_SERVICE_USER:-${SUDO_USER:-}}"
[[ -n "${SERVICE_USER}" && "${SERVICE_USER}" != "root" ]] || fail "unable to select service user; run through sudo or set INKPI_SERVICE_USER"
id "${SERVICE_USER}" >/dev/null 2>&1 || fail "service user does not exist: ${SERVICE_USER}"

SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
[[ -n "${SERVICE_HOME}" && -d "${SERVICE_HOME}" ]] || fail "home directory not found for ${SERVICE_USER}"

# --- Validate release contents ---
[[ -f "${SCRIPT_DIR}/VERSION" ]] || fail "VERSION file not found in release"
VERSION="$(cat "${SCRIPT_DIR}/VERSION")"
WHEEL=$(find "${SCRIPT_DIR}/backend" -name '*.whl' -print -quit 2>/dev/null)
[[ -n "${WHEEL}" ]] || fail "no wheel file found in backend/"
[[ -d "${SCRIPT_DIR}/frontend/dist" ]] || fail "frontend/dist not found"
[[ -f "${SCRIPT_DIR}/frontend/dist/index.html" ]] || fail "frontend/dist/index.html not found"
[[ -f "${SCRIPT_DIR}/frontend/dist/eink.html" ]] || fail "frontend/dist/eink.html not found"

echo "Installing InkPi v${VERSION} to ${INSTALL_DIR}..."

# --- Handle existing installation ---
if [[ -d "${INSTALL_DIR}/venv" ]]; then
  echo "Existing installation detected at ${INSTALL_DIR}. Upgrading..."
  systemctl stop inkpi-display.service inkpi-api.service inkpi-network-helper.service 2>/dev/null || true
  rm -rf "${INSTALL_DIR}/venv"
  rm -rf "${INSTALL_DIR}/frontend/dist"
fi

# --- Create install directory ---
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 "${INSTALL_DIR}"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 "${INSTALL_DIR}/bin"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 "${INSTALL_DIR}/frontend"

# --- Install Python venv + wheel ---
echo "Setting up Python environment..."
python3 -m venv "${INSTALL_DIR}/venv"
chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}/venv"

# Install wheel (contains the inkpi package with all dependencies)
runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/venv/bin/pip" install --quiet "${WHEEL}"

# Install rpi-specific hardware dependencies
runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/venv/bin/pip" install --quiet \
  'lgpio>=0.2.2.0' 'rpi-gpio>=0.7.1' 'spidev>=3.6' 'gpiozero>=2.0'

# Verify entry points were created
for cmd in inkpi-api inkpi-display inkpi-network-helper; do
  [[ -x "${INSTALL_DIR}/venv/bin/${cmd}" ]] || fail "missing entry point: ${cmd}"
done

# --- Install Playwright Chromium ---
echo "Installing Chromium for e-ink rendering..."
if ! "${INSTALL_DIR}/venv/bin/python" -m playwright install-deps chromium 2>&1; then
  echo "WARNING: Playwright system dependencies failed to install. E-ink rendering may not work." >&2
  echo "Install manually: apt install libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2" >&2
fi
runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/venv/bin/python" -m playwright install chromium

# --- Copy frontend dist ---
echo "Installing frontend..."
cp -r "${SCRIPT_DIR}/frontend/dist" "${INSTALL_DIR}/frontend/dist"
chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}/frontend/dist"

# --- Validate secrets ---
CONFIG_DIR="${SERVICE_HOME}/.config/inkpi"
API_ENV="${CONFIG_DIR}/api.env"
[[ -d "${CONFIG_DIR}" ]] || fail "missing config directory: ${CONFIG_DIR} (create with: mkdir -p ${CONFIG_DIR} && chmod 700 ${CONFIG_DIR})"
[[ $(stat -c '%U' "${CONFIG_DIR}") == "${SERVICE_USER}" ]] || fail "${CONFIG_DIR} must be owned by ${SERVICE_USER}"
if [[ -n "$(find "${CONFIG_DIR}" -maxdepth 0 -perm /077 -print -quit)" ]]; then
  fail "${CONFIG_DIR} must not be accessible by group/others (use chmod 700)"
fi
[[ -f "${API_ENV}" ]] || fail "missing ${API_ENV}; copy env/api.env.example and set secrets first"
if [[ -n "$(find "${API_ENV}" -perm /077 -print -quit)" ]]; then
  fail "${API_ENV} must not be readable or writable by group/others (use chmod 600)"
fi
[[ $(stat -c '%U' "${API_ENV}") == "${SERVICE_USER}" ]] || fail "${API_ENV} must be owned by ${SERVICE_USER}"
grep -Eq '^[[:space:]]*INKPI_ADMIN_TOKEN=.+$' "${API_ENV}" || fail "INKPI_ADMIN_TOKEN required in ${API_ENV}"

# --- Add user to hardware groups ---
for group in spi gpio; do
  if getent group "${group}" >/dev/null && ! id -nG "${SERVICE_USER}" | tr ' ' '\n' | grep -qx "${group}"; then
    usermod -a -G "${group}" "${SERVICE_USER}"
  fi
done

# --- Install systemd units ---
echo "Installing systemd services..."
BACKEND_BIN="${INSTALL_DIR}/venv/bin"
FRONTEND_DIST="${INSTALL_DIR}/frontend/dist"
SERVICE_PATH="${BACKEND_BIN}:${SERVICE_HOME}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

install_unit() {
  local template="$1" target_name="$2"
  local target="/etc/systemd/system/${target_name}"
  local temporary
  temporary="$(mktemp)"
  sed \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
    -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
    -e "s|__SERVICE_PATH__|${SERVICE_PATH}|g" \
    -e "s|__WORKDIR__|${INSTALL_DIR}|g" \
    -e "s|__FRONTEND_DIST__|${FRONTEND_DIST}|g" \
    -e "s|__BACKEND_BIN__|${BACKEND_BIN}|g" \
    "${SCRIPT_DIR}/systemd/${template}" > "${temporary}"
  if grep -Eq '__[A-Z0-9_]+__' "${temporary}"; then
    rm -f "${temporary}"
    fail "unresolved placeholder in ${template}"
  fi
  if [[ -f "${target}" ]]; then
    cp -a "${target}" "${target}.bak.$(date +%Y%m%d%H%M%S)"
  fi
  install -m 0644 "${temporary}" "${target}"
  rm -f "${temporary}"
}

install_unit inkpi-network-helper.service inkpi-network-helper.service
install_unit inkpi-api.service inkpi-api.service
install_unit inkpi-display.service inkpi-display.service

if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze verify \
    /etc/systemd/system/inkpi-network-helper.service \
    /etc/systemd/system/inkpi-api.service \
    /etc/systemd/system/inkpi-display.service 2>/dev/null || true
fi

systemctl daemon-reload
systemctl disable --now eink-dashboard.service inkpi-core.service inkpi-admin.service 2>/dev/null || true
systemctl enable --now inkpi-network-helper.service
systemctl enable --now inkpi-api.service
systemctl enable --now inkpi-display.service

# --- Copy uninstaller to install dir ---
if [[ -f "${SCRIPT_DIR}/uninstall.sh" ]]; then
  install -m 0755 "${SCRIPT_DIR}/uninstall.sh" "${INSTALL_DIR}/uninstall.sh"
fi

# --- Health check ---
echo "Waiting for services..."
for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 1
done

if ! curl -fsS http://127.0.0.1:8080/api/health >/dev/null; then
  systemctl --no-pager --full status inkpi-network-helper.service inkpi-api.service inkpi-display.service || true
  fail "API health check failed"
fi

systemctl is-active --quiet inkpi-network-helper.service || fail "network helper is not active"
systemctl is-active --quiet inkpi-api.service || fail "API is not active"
systemctl is-active --quiet inkpi-display.service || fail "display service is not active"

echo ""
echo "InkPi v${VERSION} installed successfully."
echo "  Web UI:  http://$(hostname -I | awk '{print $1}'):8080/"
echo "  Install: ${INSTALL_DIR}"
echo "  Config:  ${CONFIG_DIR}"
echo "  Status:  systemctl status inkpi-api inkpi-display inkpi-network-helper"
echo ""
echo "To uninstall: sudo bash ${INSTALL_DIR}/uninstall.sh"
