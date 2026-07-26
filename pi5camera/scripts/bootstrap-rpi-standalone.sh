#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="/usr/bin/python3"
VENV_DIR="${PROJECT_ROOT}/.venv"
SKIP_APT=0

APT_PACKAGES=(
  python3-picamera2
  python3-venv
  python3-dev
  python3-libcamera
)

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-rpi-standalone.sh [--skip-apt]

Prepare standalone pi5camera on Raspberry Pi OS by:
1. Installing the required system packages with apt
2. Creating .venv with /usr/bin/python3 -m venv --system-site-packages
3. Running uv sync --active --extra dev

Options:
  --skip-apt   Skip the apt install step
  --help       Show this help message
EOF
}

log() {
  printf '\n[%s] %s\n' "bootstrap" "$1"
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

assert_linux() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    fail "This bootstrap script is intended for Raspberry Pi OS or another Linux system."
  fi
}

assert_python_version() {
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info[:2] < (3, 11):
    raise SystemExit("Expected /usr/bin/python3 to be Python 3.11 or newer for pi5camera.")
PY
}

venv_can_import_picamera2() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" -c "import libcamera, picamera2" >/dev/null 2>&1
}

install_system_packages() {
  if (( SKIP_APT )); then
    log "Skipping apt install step."
    return
  fi

  require_command sudo
  require_command apt
  log "Installing required Raspberry Pi camera packages."
  sudo apt update
  sudo apt install -y "${APT_PACKAGES[@]}"
}

ensure_venv() {
  log "Recreating standalone pi5camera virtual environment."
  rm -rf "${VENV_DIR}"
  (
    cd "${PROJECT_ROOT}"
    "${PYTHON_BIN}" -m venv --system-site-packages "${VENV_DIR}"
  )
  if ! venv_can_import_picamera2; then
    local venv_output
    venv_output=$("${VENV_DIR}/bin/python" -c "import libcamera, picamera2" 2>&1 || true)
    fail "Picamera2 is still not importable inside ${VENV_DIR}. Output: ${venv_output}"
  fi
}

run_sync() {
  log "Syncing the standalone pi5camera environment."
  (
    cd "${PROJECT_ROOT}"
    source "${VENV_DIR}/bin/activate"
    uv sync --active --frozen --extra dev
  )
}

ensure_system_site_packages() {
  # Re-ensure pyvenv.cfg has include-system-site-packages = true in case
  # uv sync overwrote it.
  local CFG="${VENV_DIR}/pyvenv.cfg"
  if [[ -f "${CFG}" ]]; then
    if grep -q 'include-system-site-packages = false' "${CFG}" 2>/dev/null; then
      sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' "${CFG}"
    elif ! grep -q 'include-system-site-packages' "${CFG}" 2>/dev/null; then
      echo 'include-system-site-packages = true' >> "${CFG}"
    fi
  fi
}

run_health_checks() {
  log "Running standalone camera readiness checks."
  (
    cd "${PROJECT_ROOT}"
    uv run pi5camera doctor
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

  assert_linux
  require_command uv

  if [[ ! -x "${PYTHON_BIN}" ]]; then
    fail "Expected Python interpreter not found: ${PYTHON_BIN}"
  fi

  assert_python_version
  install_system_packages
  ensure_venv
  run_sync
  ensure_system_site_packages
  run_health_checks

  log "Standalone pi5camera bootstrap completed."
}

main "$@"
