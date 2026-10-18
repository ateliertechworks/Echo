#!/usr/bin/env bash
set -Eeuo pipefail

# Replace these values before publishing the installer.
OWNER="ateliertechworks"
REPOSITORY="Echo"
VERSION="v1.0.0"

ARCHIVE_NAME="Echo-Linux-Installer.tar.gz"
CHECKSUMS_NAME="SHA256SUMS"
RELEASE_URL="https://github.com/${OWNER}/${REPOSITORY}/releases/download/${VERSION}"

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
    # shellcheck disable=SC1091
    . /etc/os-release
    [[ "${ID:-}" == "ubuntu" ]] || fail "Echo supports Ubuntu Linux amd64 only; detected ${PRETTY_NAME:-an unsupported distribution}."
  else
    fail "Cannot identify the Linux distribution."
  fi
}

check_not_root() {
  [[ "$EUID" -ne 0 ]] || fail "Run this command as your normal logged-in user, without sudo. The main installer requests sudo when needed."
}

check_platform
check_not_root
require_command curl
require_command tar
require_command sha256sum

REAL_USER="${SUDO_USER:-$(id -un)}"
export USER="$REAL_USER"
TEMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

archive_path="$TEMP_DIR/$ARCHIVE_NAME"
checksums_path="$TEMP_DIR/$CHECKSUMS_NAME"

info "Downloading Echo release $VERSION"
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
  cd "$TEMP_DIR"
  sha256sum -c "$CHECKSUMS_NAME"
)

info "Extracting Echo release"
EXTRACT_DIR="$TEMP_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$archive_path" -C "$EXTRACT_DIR"

INSTALLER_PATH="$(find "$EXTRACT_DIR" -type f -name Echo_Linux_Installer.sh -print -quit)"
[[ -n "$INSTALLER_PATH" && -s "$INSTALLER_PATH" ]] || fail "Echo_Linux_Installer.sh was not found in the release archive."

chmod +x "$INSTALLER_PATH"
info "Starting Echo installation as $REAL_USER"
cd "$(dirname "$INSTALLER_PATH")"
exec ./Echo_Linux_Installer.sh
