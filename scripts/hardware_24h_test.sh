#!/usr/bin/env bash
set -euo pipefail

case $# in
  0) HOURS=24 ;;
  2)
    [[ "$1" == "--hours" ]] || {
      echo "Usage: scripts/hardware_24h_test.sh [--hours <number>]" >&2
      exit 2
    }
    HOURS="$2"
    ;;
  *)
    echo "Usage: scripts/hardware_24h_test.sh [--hours <number>]" >&2
    exit 2
    ;;
esac
if ! [[ "${HOURS}" =~ ^[0-9]+([.][0-9]+)?$ ]] || ! awk -v hours="${HOURS}" 'BEGIN { exit !(hours > 0) }'; then
  echo "Invalid duration: ${HOURS}" >&2
  exit 2
fi

diagnostics() {
  systemctl --no-pager --full status \
    inkpi-api.service inkpi-display.service inkpi-network-helper.service >&2 || true
  journalctl --no-pager -u inkpi-api.service -u inkpi-display.service \
    -u inkpi-network-helper.service --since '10 minutes ago' >&2 || true
}
trap diagnostics ERR

if ! command -v systemctl >/dev/null || ! command -v curl >/dev/null; then
  echo "systemctl and curl are required" >&2
  exit 2
fi

SECONDS_TOTAL=$(awk -v hours="${HOURS}" 'BEGIN { printf "%d", hours * 3600 }')
if ((SECONDS_TOTAL < 1)); then
  echo "Duration must be at least one second" >&2
  exit 2
fi
DEADLINE=$((SECONDS + SECONDS_TOTAL))

while ((SECONDS < DEADLINE)); do
  systemctl is-active --quiet inkpi-api.service
  systemctl is-active --quiet inkpi-display.service
  systemctl is-active --quiet inkpi-network-helper.service
  curl -fsS http://127.0.0.1:8080/api/health >/dev/null
  sleep 60
done

echo "${HOURS}h hardware service-health run completed"
