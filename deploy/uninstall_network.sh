#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID} -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
systemctl disable --now inkpi-network.service 2>/dev/null || true
rm -f /etc/systemd/system/inkpi-network.service
systemctl daemon-reload
echo "InkPi network service removed. Configuration and releases were preserved."
