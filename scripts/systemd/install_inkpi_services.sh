#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SERVICES=(inkpi-display.service inkpi-core.service inkpi-admin.service)

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/systemd/install_inkpi_services.sh" >&2
  exit 1
fi

SERVICE_USER="${SUDO_USER:-${USER}}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
UV_BIN="$(command -v uv || true)"

if [[ -z "${UV_BIN}" ]]; then
  for candidate in "${SERVICE_HOME}/.local/bin/uv" "${SERVICE_HOME}/.cargo/bin/uv"; do
    if [[ -x "${candidate}" ]]; then
      UV_BIN="${candidate}"
      break
    fi
  done
fi

if [[ -z "${UV_BIN}" ]]; then
  echo "uv not found for ${SERVICE_USER}" >&2
  exit 1
fi

SERVICE_PATH="$(dirname "${UV_BIN}"):/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

for service in "${SERVICES[@]}"; do
  template="${SCRIPT_DIR}/${service}"
  target="/etc/systemd/system/${service}"
  if [[ -f "${target}" ]]; then
    cp "${target}" "${target}.bak.$(date +%Y%m%d%H%M%S)"
  fi
  sed \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
    -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
    -e "s|__SERVICE_PATH__|${SERVICE_PATH}|g" \
    -e "s|__WORKDIR__|${PROJECT_ROOT}|g" \
    -e "s|__UV_BIN__|${UV_BIN}|g" \
    "${template}" > "${target}"
  chmod 0644 "${target}"
done

systemctl daemon-reload
systemctl disable --now eink-dashboard.service 2>/dev/null || true
systemctl reset-failed eink-dashboard.service 2>/dev/null || true
systemctl enable inkpi-display.service inkpi-core.service inkpi-admin.service

# Keep hardware ownership unambiguous during install and upgrades.
systemctl stop inkpi-admin.service 2>/dev/null || true
systemctl stop inkpi-core.service 2>/dev/null || true
systemctl restart inkpi-display.service
systemctl start inkpi-core.service
systemctl start inkpi-admin.service

echo "InkPi services installed."
echo "Check: systemctl status inkpi-display.service inkpi-core.service inkpi-admin.service"
