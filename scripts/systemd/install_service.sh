#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="eink-dashboard.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEMPLATE_FILE="${SCRIPT_DIR}/eink-dashboard.service"
TARGET_FILE="/etc/systemd/system/${SERVICE_NAME}"

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo "Service template not found: ${TEMPLATE_FILE}" >&2
  exit 1
fi

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/systemd/install_service.sh" >&2
  exit 1
fi

SERVICE_USER="${SUDO_USER:-${USER}}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"

if [[ -z "${SERVICE_HOME}" || ! -d "${SERVICE_HOME}" ]]; then
  echo "Cannot resolve home directory for user: ${SERVICE_USER}" >&2
  exit 1
fi

UV_BIN="$(command -v uv || true)"
if [[ -z "${UV_BIN}" ]]; then
  for candidate in \
    "${SERVICE_HOME}/.local/bin/uv" \
    "${SERVICE_HOME}/.cargo/bin/uv"; do
    if [[ -x "${candidate}" ]]; then
      UV_BIN="${candidate}"
      break
    fi
  done
fi

if [[ -z "${UV_BIN}" ]]; then
  echo "uv not found for user ${SERVICE_USER}. Install uv for this user first." >&2
  exit 1
fi

SERVICE_PATH="$(dirname "${UV_BIN}"):/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

UNIT_EXISTS_BEFORE=false
UNIT_ENABLED_BEFORE=false
UNIT_ACTIVE_BEFORE=false

if systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  UNIT_EXISTS_BEFORE=true
fi

if systemctl is-enabled "${SERVICE_NAME}" >/dev/null 2>&1; then
  UNIT_ENABLED_BEFORE=true
fi

if systemctl is-active --quiet "${SERVICE_NAME}"; then
  UNIT_ACTIVE_BEFORE=true
fi

tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

sed \
  -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
  -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
  -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
  -e "s|__SERVICE_PATH__|${SERVICE_PATH}|g" \
  -e "s|__WORKDIR__|${PROJECT_ROOT}|g" \
  -e "s|__UV_BIN__|${UV_BIN}|g" \
  "${TEMPLATE_FILE}" > "${tmp_file}"

if [[ -f "${TARGET_FILE}" ]]; then
  backup_file="${TARGET_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  cp "${TARGET_FILE}" "${backup_file}"
  echo "Backed up existing unit file: ${backup_file}"
fi

install -m 0644 "${tmp_file}" "${TARGET_FILE}"

systemctl daemon-reload

if [[ "${UNIT_EXISTS_BEFORE}" == "false" ]]; then
  systemctl enable --now "${SERVICE_NAME}"
  echo "Installed and started ${SERVICE_NAME} (new install)"
else
  if [[ "${UNIT_ENABLED_BEFORE}" == "true" ]]; then
    systemctl enable "${SERVICE_NAME}" >/dev/null
  fi

  if [[ "${UNIT_ACTIVE_BEFORE}" == "true" ]]; then
    systemctl restart "${SERVICE_NAME}"
    echo "Upgraded ${SERVICE_NAME} and restarted (service was running)"
  else
    echo "Upgraded ${SERVICE_NAME}; service remains stopped (service was not running)"
  fi
fi

echo "Enable state before upgrade: ${UNIT_ENABLED_BEFORE}"
echo "Active state before upgrade: ${UNIT_ACTIVE_BEFORE}"
echo "Check status:               systemctl status ${SERVICE_NAME}"
echo "View logs:                  journalctl -u ${SERVICE_NAME} -f"
