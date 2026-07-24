#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
SERVICE_NAME="inkpi-host-agent.service"
TEMPLATE="${SCRIPT_DIR}/systemd/${SERVICE_NAME}"
TARGET="/etc/systemd/system/${SERVICE_NAME}"

fail() {
  echo "InkPi host-agent install failed: $*" >&2
  exit 1
}

if [[ $(uname -s) != "Linux" ]]; then
  fail "this installer must run on Linux"
fi
if [[ ${EUID} -ne 0 ]]; then
  fail "run with: sudo bash deploy/install_host_agent.sh"
fi

SERVICE_USER="${INKPI_SERVICE_USER:-${SUDO_USER:-}}"
if [[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]]; then
  fail "unable to select an unprivileged service user; run through sudo or set INKPI_SERVICE_USER"
fi
id "${SERVICE_USER}" >/dev/null 2>&1 || fail "service user does not exist: ${SERVICE_USER}"

SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
[[ -n "${SERVICE_HOME}" && -d "${SERVICE_HOME}" ]] || fail "home directory not found for ${SERVICE_USER}"
[[ -f "${BACKEND_DIR}/pyproject.toml" ]] || fail "backend project not found at ${BACKEND_DIR}"

BASE_PATH="${SERVICE_HOME}/.local/bin:${SERVICE_HOME}/.cargo/bin:${SERVICE_HOME}/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
find_user_command() {
  runuser -u "${SERVICE_USER}" -- env HOME="${SERVICE_HOME}" PATH="${BASE_PATH}" \
    sh -c 'command -v "$1"' _ "$1" 2>/dev/null || true
}

UV_BIN="$(find_user_command uv)"
[[ -n "${UV_BIN}" ]] || fail "uv is not installed for ${SERVICE_USER}"
SERVICE_PATH="$(dirname "${UV_BIN}"):${BASE_PATH}"
run_as_service_user() {
  runuser -u "${SERVICE_USER}" -- env HOME="${SERVICE_HOME}" PATH="${SERVICE_PATH}" "$@"
}

CONFIG_DIR="${SERVICE_HOME}/.config/inkpi"
ENV_FILE="${CONFIG_DIR}/host-agent.env"
CREDENTIALS_FILE="${CONFIG_DIR}/host-agent.json"
[[ -d "${CONFIG_DIR}" ]] || fail "missing protected configuration directory: ${CONFIG_DIR}"
[[ $(stat -c '%U' "${CONFIG_DIR}") == "${SERVICE_USER}" ]] || fail "${CONFIG_DIR} must be owned by ${SERVICE_USER}"
if [[ -n "$(find "${CONFIG_DIR}" -maxdepth 0 -perm /077 -print -quit)" ]]; then
  fail "${CONFIG_DIR} must not be accessible by group/others (use chmod 700)"
fi
[[ -f "${ENV_FILE}" ]] || fail "missing ${ENV_FILE}; copy deploy/env/host-agent.env.example and configure it first"
if [[ -n "$(find "${ENV_FILE}" -perm /077 -print -quit)" ]]; then
  fail "${ENV_FILE} must not be readable or writable by group/others (use chmod 600)"
fi
[[ $(stat -c '%U' "${ENV_FILE}") == "${SERVICE_USER}" ]] || fail "${ENV_FILE} must be owned by ${SERVICE_USER}"
grep -Eq '^[[:space:]]*INKPI_API_URL=.+$' "${ENV_FILE}" || fail "INKPI_API_URL is required in ${ENV_FILE}"
if ! grep -Eq '^[[:space:]]*INKPI_AGENT_ENROLLMENT_TOKEN=.+$' "${ENV_FILE}" && [[ ! -f "${CREDENTIALS_FILE}" ]]; then
  fail "set INKPI_AGENT_ENROLLMENT_TOKEN for first registration"
fi
if [[ -f "${CREDENTIALS_FILE}" ]]; then
  [[ $(stat -c '%U' "${CREDENTIALS_FILE}") == "${SERVICE_USER}" ]] || fail "${CREDENTIALS_FILE} must be owned by ${SERVICE_USER}"
  if [[ -n "$(find "${CREDENTIALS_FILE}" -perm /077 -print -quit)" ]]; then
    fail "${CREDENTIALS_FILE} must not be readable or writable by group/others (use chmod 600)"
  fi
fi

echo "Preparing host-agent Python dependencies for ${SERVICE_USER}..."
run_as_service_user "${UV_BIN}" sync --project "${BACKEND_DIR}"

BACKEND_BIN="${BACKEND_DIR}/.venv/bin"
[[ -x "${BACKEND_BIN}/inkpi-host-agent" ]] || fail "missing backend executable: ${BACKEND_BIN}/inkpi-host-agent"

temporary="$(mktemp)"
trap 'rm -f "${temporary}"' EXIT
sed \
  -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
  -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
  -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
  -e "s|__SERVICE_PATH__|${SERVICE_PATH}|g" \
  -e "s|__WORKDIR__|${BACKEND_DIR}|g" \
  -e "s|__BACKEND_BIN__|${BACKEND_BIN}|g" \
  "${TEMPLATE}" > "${temporary}"
grep -Eq '__[A-Z0-9_]+__' "${temporary}" && fail "unresolved placeholder in ${TEMPLATE}"

if [[ -f "${TARGET}" ]]; then
  cp -a "${TARGET}" "${TARGET}.bak.$(date +%Y%m%d%H%M%S)"
fi
install -m 0644 "${temporary}" "${TARGET}"

if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze verify "${TARGET}"
fi

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"
sleep 2
if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
  systemctl --no-pager --full status "${SERVICE_NAME}" || true
  fail "host agent is not active"
fi

if [[ -z "$(find_user_command codex)" ]]; then
  echo "Warning: Codex CLI is not on the service PATH; Codex reports will be unavailable." >&2
fi

echo "InkPi host-agent deployment completed."
echo "Status: systemctl status ${SERVICE_NAME}"
echo "Logs: journalctl -u ${SERVICE_NAME} -f"
