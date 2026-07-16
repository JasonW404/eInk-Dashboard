#!/usr/bin/env bash
set -euo pipefail

HOURS="${2:-24}"
if [[ "${1:-}" != "--hours" && $# -gt 0 ]]; then
  echo "Usage: scripts/hardware_24h_test.sh [--hours <number>]" >&2
  exit 2
fi
if ! [[ "${HOURS}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "Invalid duration: ${HOURS}" >&2
  exit 2
fi

SECONDS_TOTAL=$(awk -v hours="${HOURS}" 'BEGIN { printf "%d", hours * 3600 }')
DEADLINE=$((SECONDS + SECONDS_TOTAL))

while ((SECONDS < DEADLINE)); do
  systemctl is-active --quiet inkpi-api.service
  systemctl is-active --quiet inkpi-display.service
  systemctl is-active --quiet inkpi-network-helper.service
  curl -fsS http://127.0.0.1:8080/api/health >/dev/null
  sleep 60
done

echo "${HOURS}h hardware service-health run completed"
