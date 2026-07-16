#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
mkdir -p "${ROOT_DIR}/tmp"
RUN_DIR="$(mktemp -d "${ROOT_DIR}/tmp/smoke.XXXXXX")"
PORT="${INKPI_SMOKE_PORT:-18080}"
API_PID=""
DISPLAY_PID=""

cleanup() {
  [[ -z "${DISPLAY_PID}" ]] || kill "${DISPLAY_PID}" 2>/dev/null || true
  [[ -z "${API_PID}" ]] || kill "${API_PID}" 2>/dev/null || true
  [[ -z "${DISPLAY_PID}" ]] || wait "${DISPLAY_PID}" 2>/dev/null || true
  [[ -z "${API_PID}" ]] || wait "${API_PID}" 2>/dev/null || true
  rm -rf "${RUN_DIR}"
}
trap cleanup EXIT

cd "${BACKEND_DIR}"
uv run inkpi-api \
  --host 127.0.0.1 \
  --port "${PORT}" \
  --database-url "sqlite+pysqlite:///${RUN_DIR}/inkpi.db" \
  --web-dist "${FRONTEND_DIR}/dist" \
  --render-base-url "http://127.0.0.1:${PORT}" >"${RUN_DIR}/api.log" 2>&1 &
API_PID=$!

for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null && break
  sleep 0.25
done
curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null
curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null

uv run inkpi-display --api-url "http://127.0.0.1:${PORT}" \
  --poll-seconds 0.25 --debounce-seconds 0 >"${RUN_DIR}/display.log" 2>&1 &
DISPLAY_PID=$!

curl -fsS -X POST "http://127.0.0.1:${PORT}/api/todos" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Smoke test frame"}' >/dev/null

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/settings/system" | grep -Eq '"last_refresh":"'; then
    echo "API + display smoke test passed"
    exit 0
  fi
  sleep 0.25
done

echo "Display refresh telemetry was not observed" >&2
tail -50 "${RUN_DIR}/api.log" >&2 || true
tail -50 "${RUN_DIR}/display.log" >&2 || true
exit 1
