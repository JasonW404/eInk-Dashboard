#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="${ROOT_DIR}/packaging"
OUTPUT_DIR="${ROOT_DIR}/build/standalone"

rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

cd "${PACKAGING_DIR}"
"${ROOT_DIR}/backend/.venv/bin/pyinstaller" \
  --noconfirm --clean \
  --distpath "${OUTPUT_DIR}" \
  --workpath "${ROOT_DIR}/build/pyinstaller/cloud" \
  inkpi-cloud.spec
"${ROOT_DIR}/backend/.venv/bin/pyinstaller" \
  --noconfirm --clean \
  --distpath "${OUTPUT_DIR}" \
  --workpath "${ROOT_DIR}/build/pyinstaller/display" \
  inkpi-display.spec
"${ROOT_DIR}/backend/.venv/bin/pyinstaller" \
  --noconfirm --clean \
  --distpath "${OUTPUT_DIR}" \
  --workpath "${ROOT_DIR}/build/pyinstaller/network" \
  inkpi-network.spec
"${ROOT_DIR}/backend/.venv/bin/pyinstaller" \
  --noconfirm --clean \
  --distpath "${OUTPUT_DIR}" \
  --workpath "${ROOT_DIR}/build/pyinstaller/host-agent" \
  inkpi-host-agent.spec

"${OUTPUT_DIR}/inkpi-cloud/inkpi-api" --help >/dev/null
"${OUTPUT_DIR}/inkpi-display/inkpi-display" --help >/dev/null
"${OUTPUT_DIR}/inkpi-network/inkpi-network" --help >/dev/null
"${OUTPUT_DIR}/inkpi-host-agent/inkpi-host-agent" --help >/dev/null
