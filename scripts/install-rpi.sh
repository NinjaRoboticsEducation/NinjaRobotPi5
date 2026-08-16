#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
VERSION_FILE="${SCRIPT_DIR}/install-versions.env"
BOOT_CONFIG="${NINJAROBOT_BOOT_CONFIG:-/boot/firmware/config.txt}"
WHISPER_DIR="${NINJAROBOT_WHISPER_DIR:-${HOME}/whisper.cpp}"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/ninjarobot_pi5"
LOG_FILE="${STATE_DIR}/installer.log"
ASSUME_YES=0
CHECK_ONLY=0
DRY_RUN=0

SYSTEM_PACKAGES=(
  alsa-utils
  avahi-daemon
  build-essential
  ca-certificates
  cmake
  curl
  git
  i2c-tools
  libnss-mdns
  libportaudio2
  pkg-config
  portaudio19-dev
  python3-dev
  python3-libcamera
  python3-picamera2
  rpicam-apps
  swig
)

usage() {
  cat <<'EOF'
Usage: ./install.sh [--yes] [--check] [--dry-run]

Install the Raspberry Pi system tools, uv, Ollama, whisper.cpp, locked Python
dependencies, camera bridge, private configuration directories, and the
GPIO12/GPIO13 hardware-PWM boot configuration required by NinjaRobotPi5.

Options:
  --yes       Accept the installation summary without the final prompt.
  --check     Read-only readiness check; do not install or change anything.
  --dry-run   Print the planned high-level operations and exit.
  --help      Show this help.

The installer never downloads an Ollama model, starts NinjaRobotAgent, moves a
servo, captures media, or reboots the Raspberry Pi.
EOF
}

log() { printf '\n[%s] %s\n' "NinjaRobot installer" "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"; }

load_versions() {
  [[ -f "${VERSION_FILE}" ]] || fail "Missing installer version manifest: ${VERSION_FILE}"
  # shellcheck disable=SC1090
  source "${VERSION_FILE}"
  : "${UV_VERSION:?}" "${OLLAMA_VERSION:?}" "${WHISPER_CPP_COMMIT:?}" "${WHISPER_MODEL:?}"
}

check_platform() {
  [[ "${EUID}" -ne 0 ]] || fail "Run ./install.sh as your normal user, not with sudo."
  [[ "$(uname -s)" == "Linux" ]] || fail "This installer supports Raspberry Pi OS only."
  [[ "$(uname -m)" == "aarch64" ]] || fail "64-bit Raspberry Pi OS (aarch64) is required."
  [[ -r /proc/device-tree/model ]] || fail "Raspberry Pi model information is unavailable."
  grep -aq "Raspberry Pi 5" /proc/device-tree/model || fail "A Raspberry Pi 5 is required."
  [[ -r /etc/os-release ]] || fail "Could not identify Raspberry Pi OS."
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" == "raspbian" || "${ID:-}" == "debian" ]] || \
    fail "Raspberry Pi OS or its Debian base is required."
  [[ -e /dev/i2c-1 ]] || fail "I2C is not enabled. Enable it in raspi-config and reboot."
  [[ -e /dev/spidev0.0 ]] || fail "SPI is not enabled. Enable it in raspi-config and reboot."
  [[ -f "${PROJECT_ROOT}/uv.lock" ]] || fail "Run this installer from a NinjaRobotPi5 clone."
}

show_plan() {
  cat <<EOF

NinjaRobotPi5 will:
  - install Raspberry Pi OS build, camera, audio, I2C, and mDNS packages
  - install uv ${UV_VERSION} and Ollama ${OLLAMA_VERSION}
  - build whisper.cpp commit ${WHISPER_CPP_COMMIT} in ${WHISPER_DIR}
  - download the multilingual whisper ${WHISPER_MODEL} model
  - back up and update ${BOOT_CONFIG} for GPIO12/GPIO13 hardware PWM
  - create private per-user configuration directories
  - install the exact locked NinjaRobotPi5 hardware dependencies

It will not pull an Ollama model, start NinjaRobotAgent, access robot hardware,
capture camera/microphone data, move the wheels, reboot, or overwrite existing
NinjaRobot configuration files.
EOF
}

confirm_plan() {
  ((ASSUME_YES)) && return
  read -r -p "Continue? Type INSTALL to proceed: " answer
  [[ "${answer}" == "INSTALL" ]] || fail "Installation cancelled; no changes were made."
}

install_system_packages() {
  log "Installing Raspberry Pi OS packages."
  sudo apt update
  sudo apt install -y "${SYSTEM_PACKAGES[@]}"
}

install_uv() {
  if command -v uv >/dev/null 2>&1 && [[ "$(uv --version)" == "uv ${UV_VERSION}"* ]]; then
    log "uv ${UV_VERSION} is already installed."
    return
  fi
  log "Installing uv ${UV_VERSION}."
  local installer
  installer="$(mktemp)"
  trap 'rm -f -- "${installer:-}"' RETURN
  curl --fail --location --silent --show-error \
    "https://astral.sh/uv/${UV_VERSION}/install.sh" --output "${installer}"
  UV_NO_MODIFY_PATH=1 sh "${installer}"
  export PATH="${HOME}/.local/bin:${PATH}"
  require_command uv
  [[ "$(uv --version)" == "uv ${UV_VERSION}"* ]] || fail "Unexpected uv version after install."
  rm -f -- "${installer}"
  trap - RETURN
}

install_ollama() {
  if command -v ollama >/dev/null 2>&1 && ollama --version 2>/dev/null | grep -q "${OLLAMA_VERSION}"; then
    log "Ollama ${OLLAMA_VERSION} is already installed."
  else
    log "Installing Ollama ${OLLAMA_VERSION}; no model will be downloaded."
    local installer
    installer="$(mktemp)"
    trap 'rm -f -- "${installer:-}"' RETURN
    curl --fail --location --silent --show-error \
      https://ollama.com/install.sh --output "${installer}"
    OLLAMA_VERSION="${OLLAMA_VERSION}" sh "${installer}"
    rm -f -- "${installer}"
    trap - RETURN
  fi
  sudo systemctl enable --now ollama
  command -v ollama >/dev/null 2>&1 || fail "Ollama installation did not provide its CLI."
}

install_whisper_cpp() {
  log "Preparing whisper.cpp at ${WHISPER_DIR}."
  if [[ -e "${WHISPER_DIR}" && ! -d "${WHISPER_DIR}/.git" ]]; then
    fail "${WHISPER_DIR} exists but is not a Git checkout; move it aside and rerun."
  fi
  if [[ ! -d "${WHISPER_DIR}/.git" ]]; then
    git clone https://github.com/ggml-org/whisper.cpp.git "${WHISPER_DIR}"
  fi
  [[ -z "$(git -C "${WHISPER_DIR}" status --porcelain)" ]] || \
    fail "${WHISPER_DIR} has local changes; preserve or commit them before rerunning."
  git -C "${WHISPER_DIR}" fetch --quiet origin "${WHISPER_CPP_COMMIT}"
  git -C "${WHISPER_DIR}" checkout --quiet --detach "${WHISPER_CPP_COMMIT}"
  cmake -S "${WHISPER_DIR}" -B "${WHISPER_DIR}/build" \
    -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON
  cmake --build "${WHISPER_DIR}/build" --config Release -j2
  if [[ ! -f "${WHISPER_DIR}/models/ggml-${WHISPER_MODEL}.bin" ]]; then
    bash "${WHISPER_DIR}/models/download-ggml-model.sh" "${WHISPER_MODEL}"
  fi
  [[ -x "${WHISPER_DIR}/build/bin/whisper-cli" ]] || fail "whisper-cli build failed."
  [[ -f "${WHISPER_DIR}/models/ggml-${WHISPER_MODEL}.bin" ]] || fail "Whisper model missing."
}

configure_pwm() {
  [[ -f "${BOOT_CONFIG}" ]] || fail "Raspberry Pi boot config not found: ${BOOT_CONFIG}"
  log "Preparing the GPIO12/GPIO13 hardware-PWM boot configuration."
  local rendered backup
  rendered="$(mktemp)"
  trap 'rm -f -- "${rendered:-}"' RETURN
  /usr/bin/python3 "${SCRIPT_DIR}/configure_rpi_boot.py" \
    --source "${BOOT_CONFIG}" --output "${rendered}"
  if cmp -s "${BOOT_CONFIG}" "${rendered}"; then
    log "Hardware PWM boot configuration is already current."
  else
    backup="${BOOT_CONFIG}.ninjarobot-backup-$(date -u +%Y%m%dT%H%M%SZ)"
    sudo cp --archive -- "${BOOT_CONFIG}" "${backup}"
    sudo install -o root -g root -m 0644 -- "${rendered}" "${BOOT_CONFIG}"
    log "Boot configuration updated; backup: ${backup}"
  fi
  rm -f -- "${rendered}"
  trap - RETURN
}

create_user_directories() {
  log "Creating private user configuration and state directories."
  local config_home data_home
  config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
  data_home="${XDG_DATA_HOME:-${HOME}/.local/share}"
  install -d -m 0700 \
    "${config_home}/pi5buzzer" \
    "${config_home}/pi5camera" \
    "${config_home}/pi5disp" \
    "${config_home}/pi5mic" \
    "${config_home}/pi5servo" \
    "${config_home}/pi5vl53l0x" \
    "${config_home}/ninjarobot_pi5" \
    "${data_home}/ninjarobot_pi5" \
    "${STATE_DIR}"
}

sync_and_verify() {
  log "Installing locked NinjaRobotPi5 hardware dependencies."
  export PATH="${HOME}/.local/bin:${PATH}"
  require_command uv
  (
    cd "${PROJECT_ROOT}"
    uv sync --frozen --extra hardware
    ./scripts/bootstrap-rpi-camera-workspace.sh --skip-apt
    uv run --frozen --extra hardware python scripts/verify_workspace_driver_sources.py
    uv run --frozen python scripts/verify_immutable_drivers.py
  )
}

readiness_check() {
  local failed=0 config_home data_home actual_commit
  config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
  data_home="${XDG_DATA_HOME:-${HOME}/.local/share}"
  for command in git cmake uv ollama; do
    if command -v "${command}" >/dev/null 2>&1; then
      printf 'PASS: %s is available\n' "${command}"
    else
      printf 'FAIL: %s is unavailable\n' "${command}"
      failed=1
    fi
  done
  if command -v uv >/dev/null 2>&1 && [[ "$(uv --version)" == "uv ${UV_VERSION}"* ]]; then
    printf 'PASS: uv version matches %s\n' "${UV_VERSION}"
  else
    printf 'FAIL: uv version does not match %s\n' "${UV_VERSION}"
    failed=1
  fi
  if command -v ollama >/dev/null 2>&1 && ollama --version 2>/dev/null | grep -q "${OLLAMA_VERSION}"; then
    printf 'PASS: Ollama version matches %s\n' "${OLLAMA_VERSION}"
  else
    printf 'FAIL: Ollama version does not match %s\n' "${OLLAMA_VERSION}"
    failed=1
  fi
  if systemctl is-active --quiet ollama; then
    printf 'PASS: Ollama service is active\n'
  else
    printf 'FAIL: Ollama service is not active\n'
    failed=1
  fi
  for package in "${SYSTEM_PACKAGES[@]}"; do
    dpkg-query -W -f='${Status}' "${package}" 2>/dev/null | grep -q 'install ok installed' || {
      printf 'FAIL: OS package is missing: %s\n' "${package}"
      failed=1
    }
  done
  [[ -x "${WHISPER_DIR}/build/bin/whisper-cli" ]] || { printf 'FAIL: whisper-cli missing\n'; failed=1; }
  [[ -f "${WHISPER_DIR}/models/ggml-${WHISPER_MODEL}.bin" ]] || { printf 'FAIL: whisper model missing\n'; failed=1; }
  if [[ -d "${WHISPER_DIR}/.git" ]]; then
    actual_commit="$(git -C "${WHISPER_DIR}" rev-parse HEAD 2>/dev/null || true)"
    [[ "${actual_commit}" == "${WHISPER_CPP_COMMIT}" ]] || {
      printf 'FAIL: whisper.cpp is not at the reviewed commit\n'
      failed=1
    }
  else
    printf 'FAIL: whisper.cpp checkout is missing\n'
    failed=1
  fi
  for directory in \
    "${config_home}/pi5buzzer" \
    "${config_home}/pi5camera" \
    "${config_home}/pi5disp" \
    "${config_home}/pi5mic" \
    "${config_home}/pi5servo" \
    "${config_home}/pi5vl53l0x" \
    "${config_home}/ninjarobot_pi5" \
    "${data_home}/ninjarobot_pi5" \
    "${STATE_DIR}"; do
    [[ -d "${directory}" ]] || { printf 'FAIL: private directory missing: %s\n' "${directory}"; failed=1; }
  done
  if /usr/bin/python3 -s -c 'import libcamera, picamera2' >/dev/null 2>&1; then
    printf 'PASS: system Picamera2 and libcamera are importable\n'
  else
    printf 'FAIL: system Picamera2/libcamera bridge prerequisites are unavailable\n'
    failed=1
  fi
  if /usr/bin/python3 "${SCRIPT_DIR}/configure_rpi_boot.py" --source "${BOOT_CONFIG}" --check; then
    printf 'PASS: hardware PWM boot configuration is ready\n'
  else
    failed=1
  fi
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    (
      cd "${PROJECT_ROOT}"
      "${PROJECT_ROOT}/.venv/bin/python" scripts/verify_workspace_driver_sources.py &&
        "${PROJECT_ROOT}/.venv/bin/python" scripts/verify_immutable_drivers.py
    ) || failed=1
  else
    printf 'FAIL: locked project environment is missing\n'
    failed=1
  fi
  return "${failed}"
}

main() {
  while (($#)); do
    case "$1" in
      --yes) ASSUME_YES=1 ;;
      --check) CHECK_ONLY=1 ;;
      --dry-run) DRY_RUN=1 ;;
      --help|-h) usage; exit 0 ;;
      *) fail "Unknown argument: $1" ;;
    esac
    shift
  done
  load_versions
  if ((DRY_RUN)); then
    show_plan
    printf '\nDry run only: no commands were executed and no files were changed.\n'
    exit 0
  fi
  check_platform
  if ((CHECK_ONLY)); then
    readiness_check
    exit $?
  fi
  show_plan
  confirm_plan
  install -d -m 0700 "${STATE_DIR}"
  exec > >(tee -a "${LOG_FILE}") 2>&1
  install_system_packages
  install_uv
  install_ollama
  install_whisper_cpp
  configure_pwm
  create_user_directories
  sync_and_verify
  readiness_check
  log "Installation passed. Reboot once, then continue with hardware module initialization."
  printf 'The installer did not download an Ollama model. Choose and pull one in the Agent setup.\n'
}

main "$@"
