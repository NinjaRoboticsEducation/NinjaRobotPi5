#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="/usr/bin/python3"
SKIP_APT=0

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-rpi-camera-workspace.sh [--skip-apt]

Prepare the NinjaRobotPi5 root environment for Picamera2 by:
1. Installing Raspberry Pi OS camera packages
2. Keeping the normal locked NinjaRobotPi5 .venv unchanged in design
3. Syncing the locked root hardware dependencies
4. Verifying the safe system-Python camera bridge without taking a photo

Options:
  --skip-apt   Skip apt installation when the camera packages are already present
  --help       Show this help message
EOF
}

log() {
  printf '\n[%s] %s\n' "camera-bootstrap" "$1"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
  fi
}

install_system_packages() {
  if ((SKIP_APT)); then
    log "Skipping apt installation."
    return
  fi
  require_command sudo
  require_command apt
  log "Installing Raspberry Pi OS camera packages."
  sudo apt update
  sudo apt install -y python3-picamera2 python3-libcamera
}

sync_workspace() {
  log "Syncing the locked NinjaRobotPi5 hardware environment."
  (
    cd "${PROJECT_ROOT}"
    uv sync --frozen --extra hardware
  )
}

verify_environment() {
  log "Checking Picamera2 with Raspberry Pi OS Python."
  if ! "${PYTHON_BIN}" -s -c "import libcamera, picamera2" >/dev/null 2>&1; then
    fail "Picamera2 or libcamera is not importable from ${PYTHON_BIN}."
  fi
  (
    cd "${PROJECT_ROOT}"
    uv run --frozen --extra hardware python scripts/verify_immutable_drivers.py
    uv run --frozen --extra hardware python -c \
      "import ninjarobot_pi5_ide, pi5camera; print('NinjaRobotPi5 environment passed')"
    uv run --frozen --extra hardware ninjarobot_pi5_cli camera health \
      --real \
      --config config/ninjarobot_pi5.toml.example \
      --ledger "${TMPDIR:-/tmp}/ninjarobot-camera-bootstrap-health.sqlite3"
  )
}

main() {
  while (($# > 0)); do
    case "$1" in
      --skip-apt)
        SKIP_APT=1
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        fail "Unknown argument: $1"
        ;;
    esac
    shift
  done

  if [[ "$(uname -s)" != "Linux" ]]; then
    fail "This script is intended for Raspberry Pi OS."
  fi
  require_command uv
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    fail "Expected Raspberry Pi OS Python not found: ${PYTHON_BIN}"
  fi

  install_system_packages
  sync_workspace
  verify_environment
  log "Camera bridge is ready. No photograph was taken."
}

main "$@"
