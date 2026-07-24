#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOURS="24"

if [[ "${1:-}" == "--hours" && -n "${2:-}" ]]; then
  HOURS="$2"
fi

if ! [[ "$HOURS" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "Invalid hours: $HOURS"
  echo "Usage: scripts/hardware_24h_test.sh [--hours <number>]"
  exit 1
fi

SECONDS_TOTAL=$(awk -v h="$HOURS" 'BEGIN { printf "%d", h * 3600 }')
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/hardware-test-$TIMESTAMP.log"
SUMMARY_FILE="$LOG_DIR/hardware-test-$TIMESTAMP-summary.txt"

mkdir -p "$LOG_DIR"

echo "== eInk Dashboard Hardware Test =="
echo "Root: $ROOT_DIR"
echo "Duration: ${HOURS}h (${SECONDS_TOTAL}s)"
echo "Log: $LOG_FILE"
echo

echo "[Preflight] Checking SPI device..."
if [[ -e /dev/spidev0.0 || -e /dev/spidev0.1 ]]; then
  echo "  OK: SPI device found"
else
  echo "  WARN: /dev/spidev0.x not found (SPI may be disabled)"
fi

echo "[Preflight] Checking user groups..."
if id -nG | grep -Eq '(^| )(gpio|spi)( |$)'; then
  echo "  OK: user has gpio/spi group"
else
  echo "  WARN: user may not be in gpio/spi groups"
fi

echo "[Preflight] Checking Python hardware deps in uv env..."
cd "$ROOT_DIR"
uv run python - <<'PY' || true
import importlib

for mod in ("spidev", "gpiozero"):
    try:
        importlib.import_module(mod)
        print(f"  OK: {mod}")
    except Exception as exc:
        print(f"  WARN: {mod} unavailable: {exc}")
PY

echo
echo "[Run] Starting dashboard loop..."
set +e
timeout "$SECONDS_TOTAL" uv run python main.py 2>&1 | tee "$LOG_FILE"
RUN_EXIT=${PIPESTATUS[0]}
set -e

FULL_COUNT=$(grep -Ec 'reason=(full_refresh_interval_elapsed|partial_refresh_threshold_reached)' "$LOG_FILE" || true)
PARTIAL_COUNT=$(grep -Ec 'reason=regular_partial_refresh' "$LOG_FILE" || true)
SKIPPED_COUNT=$(grep -Ec 'refresh skipped reason=no_visual_change' "$LOG_FILE" || true)
DISPLAY_FAIL_COUNT=$(grep -Ec 'display=failed' "$LOG_FILE" || true)
SIMULATION_COUNT=$(grep -Ec 'hardware=simulated' "$LOG_FILE" || true)
FATAL_COUNT=$(grep -Ec 'Fatal error in main loop' "$LOG_FILE" || true)

{
  echo "== Test Summary =="
  echo "Log file: $LOG_FILE"
  echo "Run exit code: $RUN_EXIT"
  echo "Full refresh decisions: $FULL_COUNT"
  echo "Partial refresh decisions: $PARTIAL_COUNT"
  echo "Skipped refreshes (no visual change): $SKIPPED_COUNT"
  echo "Display failures: $DISPLAY_FAIL_COUNT"
  echo "Simulation mode markers: $SIMULATION_COUNT"
  echo "Fatal loop errors: $FATAL_COUNT"
  echo
  if [[ "$RUN_EXIT" -eq 124 ]]; then
    echo "Result: timeout reached as expected (test duration completed)."
  elif [[ "$RUN_EXIT" -eq 0 ]]; then
    echo "Result: process exited normally before timeout."
  else
    echo "Result: process exited unexpectedly (inspect log)."
  fi
} | tee "$SUMMARY_FILE"

echo
echo "Summary written to: $SUMMARY_FILE"