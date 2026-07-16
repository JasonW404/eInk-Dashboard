#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -s) != "Linux" ]]; then
  echo "This uninstaller must run on Linux." >&2
  exit 1
fi
if [[ ${EUID} -ne 0 ]]; then
  echo "Run with: sudo bash deploy/uninstall_pi.sh" >&2
  exit 1
fi

units=(inkpi-display.service inkpi-api.service inkpi-network-helper.service)
systemctl disable --now "${units[@]}" 2>/dev/null || true
for unit in "${units[@]}"; do
  rm -f "/etc/systemd/system/${unit}"
done
systemctl daemon-reload
systemctl reset-failed "${units[@]}" 2>/dev/null || true

echo "InkPi Pi services removed. Application data, environment files, and backups were preserved."
