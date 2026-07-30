#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECONFIGURE=false

fail() { echo "InkPi network binary install failed: $*" >&2; exit 1; }
usage() { echo "Usage: sudo ./install.sh [--reconfigure]"; }

while (($#)); do
  case "$1" in
    --reconfigure) RECONFIGURE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ ${EUID} -eq 0 ]] || fail "run with: sudo ./install.sh"
[[ -x "${SCRIPT_DIR}/inkpi-network/inkpi-network" ]] || fail "network executable is missing"
command -v nmcli >/dev/null 2>&1 || fail "NetworkManager/nmcli is required"

case "$(uname -m)" in
  x86_64|amd64) HOST_ARCH="amd64" ;;
  aarch64|arm64) HOST_ARCH="arm64" ;;
  *) fail "unsupported architecture: $(uname -m)" ;;
esac
VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/VERSION")"
BUNDLE_ARCH="$(tr -d '[:space:]' < "${SCRIPT_DIR}/ARCH")"
[[ "${HOST_ARCH}" == "${BUNDLE_ARCH}" ]] || fail "bundle is ${BUNDLE_ARCH}, host is ${HOST_ARCH}"

CONFIG_DIR="/etc/inkpi"
NETWORK_ENV="${CONFIG_DIR}/pi-network.env"
install -d -o root -g root -m 0700 "${CONFIG_DIR}"
if [[ ! -f "${NETWORK_ENV}" || "${RECONFIGURE}" == true ]]; then
  [[ -t 0 ]] || fail "interactive input is required; run from a terminal or pre-create ${NETWORK_ENV}"
  api_url=""
  while [[ ! "${api_url}" =~ ^https?://[^[:space:]]+$ ]]; do
    read -r -p "InkPi Cloud API URL: " api_url
  done
  network_token=""
  while [[ -z "${network_token}" || "${network_token}" == *[[:space:]]* ]]; do
    read -r -s -p "Network device token from InkPi Cloud: " network_token
    echo >&2
  done
  temporary="$(mktemp)"
  {
    printf 'INKPI_API_URL=%s\n' "${api_url}"
    printf 'INKPI_NETWORK_TOKEN=%s\n' "${network_token}"
    printf 'INKPI_NETWORK_POLL_SECONDS=5\n'
  } > "${temporary}"
  install -o root -g root -m 0600 "${temporary}" "${NETWORK_ENV}"
  rm -f "${temporary}"
  unset api_url network_token
fi
[[ $(stat -c '%U:%G %a' "${NETWORK_ENV}") == "root:root 600" ]] || fail "${NETWORK_ENV} must be root:root 0600"

RELEASE_DIR="/opt/inkpi/network/${VERSION}-${HOST_ARCH}"
install -d -m 0755 "${RELEASE_DIR}"
cp -a "${SCRIPT_DIR}/inkpi-network" "${RELEASE_DIR}/"
install -m 0644 "${SCRIPT_DIR}/VERSION" "${RELEASE_DIR}/VERSION"
install -d -m 0755 /opt/inkpi/network
ln -sfn "${RELEASE_DIR}" /opt/inkpi/network/current

if [[ -f /etc/systemd/system/inkpi-network.service ]]; then
  cp -a /etc/systemd/system/inkpi-network.service \
    "/etc/systemd/system/inkpi-network.service.bak.$(date +%Y%m%d%H%M%S)"
fi
install -m 0644 "${SCRIPT_DIR}/systemd/inkpi-network.service" /etc/systemd/system/inkpi-network.service
systemd-analyze verify /etc/systemd/system/inkpi-network.service
systemctl daemon-reload
systemctl enable --now inkpi-network.service
systemctl restart inkpi-network.service
sleep 2
systemctl is-active --quiet inkpi-network.service || fail "network service is not active"
echo "InkPi network ${VERSION} (${HOST_ARCH}) installed without Python or uv."
