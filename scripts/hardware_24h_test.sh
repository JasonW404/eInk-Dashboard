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
  systemctl --no-pager --full status inkpi-display.service >&2 || true
  journalctl --no-pager -u inkpi-display.service --since '10 minutes ago' >&2 || true
}
trap diagnostics ERR

if ! command -v systemctl >/dev/null; then
  echo "systemctl is required" >&2
  exit 2
fi

SECONDS_TOTAL=$(awk -v hours="${HOURS}" 'BEGIN { printf "%d", hours * 3600 }')
if ((SECONDS_TOTAL < 1)); then
  echo "Duration must be at least one second" >&2
  exit 2
fi
DEADLINE=$((SECONDS + SECONDS_TOTAL))

while ((SECONDS < DEADLINE)); do
  systemctl is-active --quiet inkpi-display.service
  sleep 60
done

echo "${HOURS}h hardware service-health run completed"
