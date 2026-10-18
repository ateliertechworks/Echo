#!/usr/bin/env bash
set -Eeuo pipefail

# Replace these values before publishing the installer.
OWNER="ateliertechworks"
REPOSITORY="Echo"
ECHO_RELEASE_VERSION="v1.0.3"

ARCHIVE_NAME="Echo-Linux-Installer.tar.gz"
CHECKSUMS_NAME="SHA256SUMS"
RELEASE_URL="https://github.com/${OWNER}/${REPOSITORY}/releases/download/${ECHO_RELEASE_VERSION}"

info() {
  printf '[Echo installer] %s\n' "$1"
}

fail() {
  printf '[Echo installer] ERROR: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

check_platform() {
  [[ "$(uname -s)" == "Linux" ]] || fail "Echo supports Ubuntu Linux amd64 only."
  [[ "$(uname -m)" == "x86_64" ]] || fail "Echo supports Ubuntu Linux amd64 only; detected $(uname -m)."
  if [[ -r /etc/os-release ]]; then
    local os_id os_name
    os_id="$(. /etc/os-release; printf '%s' "${ID:-}")"
    os_name="$(. /etc/os-release; printf '%s' "${PRETTY_NAME:-an unsupported distribution}")"
    [[ "$os_id" == "ubuntu" ]] || fail "Echo supports Ubuntu Linux amd64 only; detected $os_name."
  else
    fail "Cannot identify the Linux distribution."
  fi
}

check_not_root() {
  [[ "$EUID" -ne 0 ]] || fail "Run this command as your normal logged-in user, without sudo. The main installer requests sudo when needed."
}

main() {
  check_platform
  check_not_root
  require_command curl
  require_command tar
  require_command sha256sum

  local real_user temp_dir archive_path checksums_path extract_dir installer_path
  real_user="${SUDO_USER:-$(id -un)}"
  export USER="$real_user"
  temp_dir="$(mktemp -d)"
  cleanup() {
    rm -rf "$temp_dir"
  }
  trap cleanup EXIT

  archive_path="$temp_dir/$ARCHIVE_NAME"
  checksums_path="$temp_dir/$CHECKSUMS_NAME"

  info "Downloading Echo release $ECHO_RELEASE_VERSION"
  curl -fsSL --retry 3 --connect-timeout 15 \
    "$RELEASE_URL/$ARCHIVE_NAME" -o "$archive_path"
  curl -fsSL --retry 3 --connect-timeout 15 \
    "$RELEASE_URL/$CHECKSUMS_NAME" -o "$checksums_path"

  [[ -s "$archive_path" ]] || fail "Downloaded archive is empty."
  [[ -s "$checksums_path" ]] || fail "Downloaded checksum file is empty."

  info "Verifying archive checksum"
  if ! grep -Eq "^[[:xdigit:]]{64}[[:space:]]+[* ]?${ARCHIVE_NAME//./\\.}$" "$checksums_path"; then
    fail "SHA256SUMS does not contain a checksum for $ARCHIVE_NAME."
  fi
  (
    cd "$temp_dir"
    sha256sum -c "$CHECKSUMS_NAME"
  )

  info "Extracting Echo release"
  extract_dir="$temp_dir/extracted"
  mkdir -p "$extract_dir"
  tar -xzf "$archive_path" -C "$extract_dir"

  installer_path="$(find "$extract_dir" -type f -name Echo_Linux_Installer.sh -print -quit)"
  [[ -n "$installer_path" && -s "$installer_path" ]] || fail "Echo_Linux_Installer.sh was not found in the release archive."

  chmod +x "$installer_path"
  info "Starting Echo installation as $real_user"
  cd "$(dirname "$installer_path")"
  exec ./Echo_Linux_Installer.sh
}

if [[ "${ECHO_INSTALLER_TEST:-0}" != "1" ]]; then
  main "$@"
fi
