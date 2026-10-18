#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

cd "$ROOT_DIR"
info "Validating installer syntax"
bash -n Echo_Linux_Installer.sh
bash -n install-echo.sh

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
)

for path in "${required_files[@]}"; do
  [[ -s "$path" ]] || fail "Required file is missing or empty: $path"
done
for path in "${required_directories[@]}"; do
  [[ -d "$path" ]] || fail "Required directory is missing: $path"
done
[[ -x dist/Echo ]] || fail "Built executable is not executable: dist/Echo"

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
  echo_app/db/migrations \
  echo_app/assets \
  .env.example \
  README_PACKAGING.md

info "Creating $CHECKSUMS_PATH"
(
  cd "$ROOT_DIR"
  sha256sum "$(basename "$ARCHIVE_PATH")" >"$(basename "$CHECKSUMS_PATH")"
)

info "Release package created"
printf '  %s\n  %s\n' "$ARCHIVE_PATH" "$CHECKSUMS_PATH"
