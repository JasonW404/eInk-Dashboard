#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/systemd"

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/install_pi.sh" >&2
  exit 1
fi

SERVICE_USER="${SUDO_USER:-${USER}}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
UV_BIN="$(command -v uv || true)"
for candidate in "${SERVICE_HOME}/.local/bin/uv" "${SERVICE_HOME}/.cargo/bin/uv"; do
  [[ -n "${UV_BIN}" ]] || [[ ! -x "${candidate}" ]] || UV_BIN="${candidate}"
done
if [[ -z "${UV_BIN}" ]]; then
  echo "uv not found for ${SERVICE_USER}" >&2
  exit 1
fi

SERVICE_PATH="$(dirname "${UV_BIN}"):/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
install_unit() {
  local template="$1"
  local target_name="$2"
  sed \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
    -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
    -e "s|__SERVICE_PATH__|${SERVICE_PATH}|g" \
    -e "s|__WORKDIR__|${PROJECT_ROOT}/backend|g" \
    -e "s|__FRONTEND_DIST__|${PROJECT_ROOT}/frontend/dist|g" \
    -e "s|__UV_BIN__|${UV_BIN}|g" \
    "${TEMPLATE_DIR}/${template}" > "/etc/systemd/system/${target_name}"
  chmod 0644 "/etc/systemd/system/${target_name}"
}

install_unit inkpi-network-helper.service inkpi-network-helper.service
install_unit inkpi-api.service inkpi-api.service
install_unit inkpi-display.service inkpi-display.service

systemctl daemon-reload
systemctl disable --now eink-dashboard.service inkpi-core.service inkpi-admin.service 2>/dev/null || true
systemctl enable inkpi-network-helper.service inkpi-api.service inkpi-display.service
systemctl restart inkpi-network-helper.service
systemctl restart inkpi-api.service
systemctl restart inkpi-display.service

echo "InkPi v1 Pi services installed."
echo "Check: systemctl status inkpi-network-helper.service inkpi-api.service inkpi-display.service"
