#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
TEMPLATE_DIR="${SCRIPT_DIR}/systemd"

fail() {
  echo "InkPi Pi install failed: $*" >&2
  exit 1
}

if [[ $(uname -s) != "Linux" ]]; then
  fail "this installer must run on Linux"
fi
if [[ ${EUID} -ne 0 ]]; then
  fail "run with: sudo bash deploy/install_pi.sh"
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
[[ -f "${FRONTEND_DIR}/package.json" ]] || fail "frontend project not found at ${FRONTEND_DIR}"

case "$(uname -m)" in
  aarch64|arm64) ;;
  *) fail "the Raspberry Pi deployment requires a 64-bit ARM OS; found $(uname -m)" ;;
esac

BASE_PATH="${SERVICE_HOME}/.local/bin:${SERVICE_HOME}/.cargo/bin:${SERVICE_HOME}/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
find_user_command() {
  runuser -u "${SERVICE_USER}" -- env HOME="${SERVICE_HOME}" PATH="${BASE_PATH}" \
    sh -c 'command -v "$1"' _ "$1" 2>/dev/null || true
}

UV_BIN="$(find_user_command uv)"
BUN_BIN="$(find_user_command bun)"
[[ -n "${UV_BIN}" ]] || fail "uv is not installed for ${SERVICE_USER}"
[[ -n "${BUN_BIN}" ]] || fail "Bun is not installed for ${SERVICE_USER}"

SERVICE_PATH="$(dirname "${UV_BIN}"):$(dirname "${BUN_BIN}"):${BASE_PATH}"
run_as_service_user() {
  runuser -u "${SERVICE_USER}" -- env HOME="${SERVICE_HOME}" PATH="${SERVICE_PATH}" "$@"
}

CONFIG_DIR="${SERVICE_HOME}/.config/inkpi"
API_ENV="${CONFIG_DIR}/api.env"
[[ -d "${CONFIG_DIR}" ]] || fail "missing protected configuration directory: ${CONFIG_DIR}"
[[ $(stat -c '%U' "${CONFIG_DIR}") == "${SERVICE_USER}" ]] || fail "${CONFIG_DIR} must be owned by ${SERVICE_USER}"
if [[ -n "$(find "${CONFIG_DIR}" -maxdepth 0 -perm /077 -print -quit)" ]]; then
  fail "${CONFIG_DIR} must not be accessible by group/others (use chmod 700)"
fi
[[ -f "${API_ENV}" ]] || fail "missing ${API_ENV}; copy deploy/env/api.env.example and set the secrets first"
if [[ -n "$(find "${API_ENV}" -perm /077 -print -quit)" ]]; then
  fail "${API_ENV} must not be readable or writable by group/others (use chmod 600)"
fi
[[ $(stat -c '%U' "${API_ENV}") == "${SERVICE_USER}" ]] || fail "${API_ENV} must be owned by ${SERVICE_USER}"
grep -Eq '^[[:space:]]*INKPI_ADMIN_TOKEN=.+$' "${API_ENV}" || fail "INKPI_ADMIN_TOKEN is required in ${API_ENV}"

echo "Preparing Python dependencies for ${SERVICE_USER}..."
run_as_service_user "${UV_BIN}" sync --project "${BACKEND_DIR}" --extra rpi

echo "Installing Chromium system dependencies..."
"${UV_BIN}" run --project "${BACKEND_DIR}" playwright install-deps chromium
echo "Installing Chromium for ${SERVICE_USER}..."
run_as_service_user "${UV_BIN}" run --project "${BACKEND_DIR}" playwright install chromium

echo "Building the React frontend..."
run_as_service_user sh -c 'cd "$1" && "$2" install --frozen-lockfile && "$2" run build' \
  _ "${FRONTEND_DIR}" "${BUN_BIN}"
[[ -f "${FRONTEND_DIR}/dist/index.html" ]] || fail "frontend build did not create dist/index.html"
[[ -f "${FRONTEND_DIR}/dist/eink.html" ]] || fail "frontend build did not create dist/eink.html"

for group in spi gpio; do
  if getent group "${group}" >/dev/null && ! id -nG "${SERVICE_USER}" | tr ' ' '\n' | grep -qx "${group}"; then
    usermod -a -G "${group}" "${SERVICE_USER}"
  fi
done

BACKEND_BIN="${BACKEND_DIR}/.venv/bin"
for command in inkpi-api inkpi-display inkpi-network-helper; do
  [[ -x "${BACKEND_BIN}/${command}" ]] || fail "missing backend executable: ${BACKEND_BIN}/${command}"
done

install_unit() {
  local template="$1"
  local target_name="$2"
  local target="/etc/systemd/system/${target_name}"
  local temporary
  temporary="$(mktemp)"
  sed \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    -e "s|__SERVICE_GROUP__|${SERVICE_GROUP}|g" \
    -e "s|__SERVICE_HOME__|${SERVICE_HOME}|g" \
    -e "s|__SERVICE_PATH__|${SERVICE_PATH}|g" \
    -e "s|__WORKDIR__|${BACKEND_DIR}|g" \
    -e "s|__FRONTEND_DIST__|${FRONTEND_DIR}/dist|g" \
    -e "s|__BACKEND_BIN__|${BACKEND_BIN}|g" \
    "${TEMPLATE_DIR}/${template}" > "${temporary}"
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
    /etc/systemd/system/inkpi-display.service
fi

systemctl daemon-reload
systemctl disable --now eink-dashboard.service inkpi-core.service inkpi-admin.service 2>/dev/null || true
systemctl enable --now inkpi-network-helper.service
systemctl enable --now inkpi-api.service
systemctl enable --now inkpi-display.service

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -fsS http://127.0.0.1:8080/api/health >/dev/null; then
  systemctl --no-pager --full status inkpi-network-helper.service inkpi-api.service inkpi-display.service || true
  fail "API health check failed"
fi
systemctl is-active --quiet inkpi-network-helper.service || fail "network helper is not active"
systemctl is-active --quiet inkpi-api.service || fail "API is not active"
systemctl is-active --quiet inkpi-display.service || fail "display service is not active"

echo "InkPi Raspberry Pi deployment completed."
echo "Web UI: http://$(hostname -I | awk '{print $1}'):8080/"
echo "Status: systemctl status inkpi-network-helper inkpi-api inkpi-display"
