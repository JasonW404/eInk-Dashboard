#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -s) != "Linux" ]]; then
  echo "This uninstaller must run on Linux." >&2
  exit 1
fi
if [[ ${EUID} -ne 0 ]]; then
  echo "Run with: sudo bash deploy/uninstall_cloud.sh" >&2
  exit 1
fi

units=(inkpi-host-agent.service inkpi-cloud.service)
systemctl disable --now "${units[@]}" 2>/dev/null || true
for unit in "${units[@]}"; do
  rm -f "/etc/systemd/system/${unit}"
done
systemctl daemon-reload
systemctl reset-failed "${units[@]}" 2>/dev/null || true

echo "InkPi cloud and HostAgent services removed. Application data, credentials, environment files, and backups were preserved."
