#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ECHO_RELEASE_VERSION="v1.0.4"
ARCHIVE_PATH="$ROOT_DIR/Echo-Linux-Installer.tar.gz"
CHECKSUMS_PATH="$ROOT_DIR/SHA256SUMS"

fail() {
  printf '[Echo release] ERROR: %s\n' "$1" >&2
  exit 1
}

info() {
  printf '[Echo release] %s\n' "$1"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

require_command bash
require_command tar
require_command sha256sum
require_command docker

cd "$ROOT_DIR"
info "Validating installer syntax"
bash -n Echo_Linux_Installer.sh
bash -n install-echo.sh
grep -Fq "ECHO_RELEASE_VERSION=\"$ECHO_RELEASE_VERSION\"" install-echo.sh \
  || fail "install-echo.sh does not target release $ECHO_RELEASE_VERSION"
grep -Fq "$ECHO_RELEASE_VERSION" README_PACKAGING.md \
  || fail "README_PACKAGING.md does not document release $ECHO_RELEASE_VERSION"

info "Building dist/Echo"
bash build_linux.sh

required_files=(
  Echo_Linux_Installer.sh
  dist/Echo
  docker-compose.yml
  Echo.desktop
  .env.example
  README_PACKAGING.md
)
required_directories=(
  echo_app/db/migrations
  echo_app/assets
  dist/Echo
)

for path in "${required_files[@]}"; do
  [[ -s "$path" ]] || fail "Required file is missing or empty: $path"
done
for path in "${required_directories[@]}"; do
  [[ -d "$path" ]] || fail "Required directory is missing: $path"
done
[[ -f dist/Echo/Echo ]] || fail "PyInstaller executable is missing: dist/Echo/Echo"
[[ -x dist/Echo/Echo ]] || fail "Built executable is not executable: dist/Echo/Echo"
[[ -d dist/Echo/_internal ]] || fail "PyInstaller _internal directory is missing: dist/Echo/_internal"

rm -f "$ARCHIVE_PATH" "$CHECKSUMS_PATH"
info "Creating $ARCHIVE_PATH"
tar -czf "$ARCHIVE_PATH" \
  --exclude='.env' \
  --exclude='*.db' \
  --exclude='*.log' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='.venv' \
  -C "$ROOT_DIR" \
  Echo_Linux_Installer.sh \
  dist/Echo \
  docker-compose.yml \
  Echo.desktop \
  --transform='s,^echo_app/db/migrations,migrations,' \
  --transform='s,^echo_app/assets,assets,' \
  echo_app/db/migrations \
  echo_app/assets \
  .env.example \
  README_PACKAGING.md

info "Creating $CHECKSUMS_PATH"
(
  cd "$ROOT_DIR"
  sha256sum "$(basename "$ARCHIVE_PATH")" >"$(basename "$CHECKSUMS_PATH")"
)

  VERIFY_DIR="$(mktemp -d)"
  cleanup() {
    rm -rf "$VERIFY_DIR"
  }
  trap cleanup EXIT
  info "Verifying extracted release package"
  tar -xzf "$ARCHIVE_PATH" -C "$VERIFY_DIR"
  [[ -f "$VERIFY_DIR/dist/Echo/Echo" ]] || fail "Extracted Echo executable is missing."
  [[ -x "$VERIFY_DIR/dist/Echo/Echo" ]] || fail "Extracted Echo executable is not executable."
  [[ -d "$VERIFY_DIR/dist/Echo/_internal" ]] || fail "Extracted PyInstaller _internal directory is missing."
  [[ -d "$VERIFY_DIR/migrations" ]] || fail "Extracted migrations are missing."
  [[ -d "$VERIFY_DIR/assets" ]] || fail "Extracted assets are missing."
  docker compose --env-file "$VERIFY_DIR/.env.example" \
    -f "$VERIFY_DIR/docker-compose.yml" config --quiet

info "Release package created"
printf '  %s\n  %s\n' "$ARCHIVE_PATH" "$CHECKSUMS_PATH"
