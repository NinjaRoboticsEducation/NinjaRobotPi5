#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]:-}"
SCRIPT_DIR=""
PROJECT_INSTALLER=""
if [[ -n "${SCRIPT_PATH}" ]]; then
  SCRIPT_DIR="$(cd -- "$(dirname -- "${SCRIPT_PATH}")" && pwd)"
  PROJECT_INSTALLER="${SCRIPT_DIR}/scripts/install-rpi.sh"
fi
REPOSITORY_URL="https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git"
INSTALL_REF="${NINJAROBOT_INSTALL_REF:-public_v07}"
INSTALL_DIR="${NINJAROBOT_INSTALL_DIR:-${HOME}/NinjaRobotPi5}"

if [[ -n "${PROJECT_INSTALLER}" && -x "${PROJECT_INSTALLER}" && -f "${SCRIPT_DIR}/uv.lock" ]]; then
  exec "${PROJECT_INSTALLER}" "$@"
fi

forwarded=()
dry_run=0
check_only=0
while (($#)); do
  case "$1" in
    --ref)
      [[ $# -ge 2 ]] || { printf 'ERROR: --ref requires a value.\n' >&2; exit 2; }
      INSTALL_REF="$2"
      shift 2
      ;;
    --install-dir)
      [[ $# -ge 2 ]] || { printf 'ERROR: --install-dir requires a value.\n' >&2; exit 2; }
      INSTALL_DIR="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      forwarded+=("$1")
      shift
      ;;
    --check)
      check_only=1
      forwarded+=("$1")
      shift
      ;;
    --help)
      cat <<'EOF'
Usage: install.sh [--ref GIT_REF] [--install-dir PATH] [installer options]

Download an exact NinjaRobotPi5 revision into a new directory, then run the
repository installer. Inside an existing checkout, this script continues to
delegate directly to scripts/install-rpi.sh.

Bootstrap options:
  --ref          Git commit, tag, or branch to install (default: public_v07).
  --install-dir  New checkout location (default: $HOME/NinjaRobotPi5).

Installer options are forwarded unchanged: --profile, --yes, --check,
--dry-run, and --help.
EOF
      exit 0
      ;;
    *)
      forwarded+=("$1")
      shift
      ;;
  esac
done

[[ -n "${INSTALL_REF}" && "${INSTALL_REF}" != -* ]] || {
  printf 'ERROR: --ref must be a non-option Git reference.\n' >&2
  exit 2
}
[[ "${INSTALL_DIR}" = /* ]] || {
  printf 'ERROR: --install-dir must be an absolute path.\n' >&2
  exit 2
}

if ((dry_run)); then
  cat <<EOF
NinjaRobot bootstrap preview
  repository: ${REPOSITORY_URL}
  revision:   ${INSTALL_REF}
  destination: ${INSTALL_DIR}

The repository would be downloaded into a private staging directory, its Git
revision and required installer files would be checked before the existing
installer is invoked. No commands were executed and no files were created.
EOF
  exit 0
fi

if ((check_only)); then
  if [[ -x "${INSTALL_DIR}/install.sh" && -f "${INSTALL_DIR}/uv.lock" ]]; then
    exec "${INSTALL_DIR}/install.sh" "${forwarded[@]}"
  fi
  printf 'ERROR: NinjaRobotPi5 is not installed at %s.\n' "${INSTALL_DIR}" >&2
  exit 1
fi

command -v git >/dev/null 2>&1 || {
  printf 'ERROR: Git is required for the bootstrap. Install Git, then retry.\n' >&2
  exit 1
}
[[ ! -e "${INSTALL_DIR}" && ! -L "${INSTALL_DIR}" ]] || {
  printf 'ERROR: Refusing to overwrite existing destination: %s\n' "${INSTALL_DIR}" >&2
  exit 1
}

install_parent="$(dirname -- "${INSTALL_DIR}")"
[[ -d "${install_parent}" && ! -L "${install_parent}" ]] || {
  printf 'ERROR: The destination parent must be an existing real directory: %s\n' \
    "${install_parent}" >&2
  exit 1
}

staging="$(mktemp -d "${install_parent}/.ninjarobot-bootstrap.XXXXXX")"
cleanup() { rm -rf -- "${staging}"; }
trap cleanup EXIT INT TERM

printf 'Downloading NinjaRobotPi5 revision %s...\n' "${INSTALL_REF}"
git clone --quiet --no-checkout --filter=blob:none -- "${REPOSITORY_URL}" "${staging}/checkout"
git -C "${staging}/checkout" checkout --quiet --detach "${INSTALL_REF}"
resolved="$(git -C "${staging}/checkout" rev-parse HEAD)"
if [[ "${INSTALL_REF}" =~ ^[0-9a-fA-F]{40}$ && "${resolved,,}" != "${INSTALL_REF,,}" ]]; then
  printf 'ERROR: Downloaded revision does not match --ref.\n' >&2
  exit 1
fi
for required in install.sh scripts/install-rpi.sh scripts/install-versions.env uv.lock; do
  [[ -f "${staging}/checkout/${required}" ]] || {
    printf 'ERROR: Downloaded revision is missing %s.\n' "${required}" >&2
    exit 1
  }
done

mv -- "${staging}/checkout" "${INSTALL_DIR}"
rmdir -- "${staging}"
trap - EXIT INT TERM
printf 'Verified revision %s at %s.\n' "${resolved}" "${INSTALL_DIR}"
exec "${INSTALL_DIR}/install.sh" "${forwarded[@]}"
