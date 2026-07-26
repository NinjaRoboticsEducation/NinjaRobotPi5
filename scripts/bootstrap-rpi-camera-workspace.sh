#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="/usr/bin/python3"
VENV_DIR="${PROJECT_ROOT}/.venv"
SKIP_APT=0

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-rpi-camera-workspace.sh [--skip-apt]

Prepare the NinjaRobotPi5 root environment for Picamera2 by:
1. Installing Raspberry Pi OS camera packages
2. Preserving any incompatible .venv as a timestamped backup
3. Creating .venv with system-site-packages enabled
4. Syncing the locked root hardware dependencies

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

venv_is_ready() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import sys
import libcamera
import picamera2

if not (3, 11) <= sys.version_info[:2] < (3, 14):
    raise SystemExit(1)
PY
}

install_system_packages() {
  if ((SKIP_APT)); then
    log "Skipping apt installation."
    return
  fi
  require_command sudo
  require_command apt
  log "Installing Raspberry Pi OS camera and virtual-environment packages."
  sudo apt update
  sudo apt install -y python3-picamera2 python3-libcamera python3-venv
}

prepare_venv() {
  if venv_is_ready; then
    log "The existing .venv already imports Picamera2; keeping it."
    return
  fi

  if [[ -e "${VENV_DIR}" ]]; then
    local backup_dir="${PROJECT_ROOT}.venv-before-camera-$(date +%Y%m%d-%H%M%S)"
    log "Moving the existing .venv to ${backup_dir}."
    mv -- "${VENV_DIR}" "${backup_dir}"
  fi

  log "Creating .venv with Raspberry Pi OS system packages enabled."
  "${PYTHON_BIN}" -m venv --system-site-packages "${VENV_DIR}"
}

sync_workspace() {
  log "Syncing the locked NinjaRobotPi5 hardware environment."
  (
    cd "${PROJECT_ROOT}"
    source "${VENV_DIR}/bin/activate"
    uv sync --active --frozen --extra hardware
  )
}

ensure_system_site_packages() {
  local venv_config="${VENV_DIR}/pyvenv.cfg"
  if [[ ! -f "${venv_config}" ]]; then
    fail "Virtual-environment configuration is missing: ${venv_config}"
  fi
  if grep -q 'include-system-site-packages = false' "${venv_config}"; then
    sed -i \
      's/include-system-site-packages = false/include-system-site-packages = true/' \
      "${venv_config}"
  elif ! grep -q 'include-system-site-packages' "${venv_config}"; then
    printf '%s\n' 'include-system-site-packages = true' >>"${venv_config}"
  fi
}

verify_environment() {
  if ! venv_is_ready; then
    fail "Picamera2 or libcamera is not importable from ${VENV_DIR}."
  fi
  (
    cd "${PROJECT_ROOT}"
    "${VENV_DIR}/bin/python" scripts/verify_immutable_drivers.py
    "${VENV_DIR}/bin/python" -c \
      "import libcamera, picamera2; print('Picamera2 import passed:', picamera2.__file__)"
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
  prepare_venv
  sync_workspace
  ensure_system_site_packages
  verify_environment
  log "Camera-capable NinjaRobotPi5 environment is ready."
}

main "$@"
