#!/usr/bin/env bash
set -euo pipefail

SOCK_DIR=$(mktemp -d)
DISPLAY_SOCK="$SOCK_DIR/display.sock"
CORE_SOCK="$SOCK_DIR/core.sock"

cleanup() {
  kill "$DISPLAY_PID" "$CORE_PID" 2>/dev/null || true
  wait "$DISPLAY_PID" "$CORE_PID" 2>/dev/null || true
  rm -rf "$SOCK_DIR"
}
trap cleanup EXIT

# Start display service (auto-enters simulation mode without hardware)
INKPI_DISPLAY_SOCKET="$DISPLAY_SOCK" uv run inkpi-display --socket "$DISPLAY_SOCK" &
DISPLAY_PID=$!
sleep 2

# Start core service
INKPI_DISPLAY_SOCKET="$DISPLAY_SOCK" \
INKPI_CORE_SOCKET="$CORE_SOCK" \
uv run inkpi-core --socket "$CORE_SOCK" --display-socket "$DISPLAY_SOCK" &
CORE_PID=$!
sleep 3

# Verify services respond
uv run inkpi-ctl --socket "$CORE_SOCK" status
uv run inkpi-ctl --socket "$CORE_SOCK" pages

echo "Smoke test passed"
