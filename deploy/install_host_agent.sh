#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="inkpi-host-agent.service"
TEMPLATE="${SCRIPT_DIR}/systemd/${SERVICE_NAME}"
TARGET="/etc/systemd/system/${SERVICE_NAME}"

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/install_host_agent.sh" >&2
  exit 1
fi

SERVICE_USER="${SUDO_USER:-${USER}}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
ENV_FILE="${SERVICE_HOME}/.config/inkpi/host-agent.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}; configure INKPI_API_URL and INKPI_AGENT_ENROLLMENT_TOKEN first." >&2
  exit 1
fi

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
temporary="$(mktemp)"
trap 'rm -f "${temporary}"' EXIT

sed \
  -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
  -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
  -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
  -e "s|__SERVICE_PATH__|${SERVICE_PATH}|g" \
  -e "s|__WORKDIR__|${PROJECT_ROOT}/backend|g" \
  -e "s|__UV_BIN__|${UV_BIN}|g" \
  "${TEMPLATE}" > "${temporary}"

if [[ -f "${TARGET}" ]]; then
  cp "${TARGET}" "${TARGET}.bak.$(date +%Y%m%d%H%M%S)"
fi
install -m 0644 "${temporary}" "${TARGET}"
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"

echo "Host agent installed."
echo "Check: systemctl status ${SERVICE_NAME}"
