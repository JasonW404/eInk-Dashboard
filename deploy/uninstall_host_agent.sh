#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -s) != "Linux" ]]; then
  echo "This uninstaller must run on Linux." >&2
  exit 1
fi
if [[ ${EUID} -ne 0 ]]; then
  echo "Run with: sudo bash deploy/uninstall_host_agent.sh" >&2
  exit 1
fi

unit="inkpi-host-agent.service"
systemctl disable --now "${unit}" 2>/dev/null || true
rm -f "/etc/systemd/system/${unit}"
systemctl daemon-reload
systemctl reset-failed "${unit}" 2>/dev/null || true

echo "InkPi host agent removed. Credentials, environment files, and backups were preserved."
