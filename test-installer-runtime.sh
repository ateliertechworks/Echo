#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VERSION="sentinel"
ECHO_INSTALLER_TEST=1 source "$ROOT_DIR/install-echo.sh"
check_platform
[[ "$ECHO_RELEASE_VERSION" == "v1.0.4" ]] || {
  printf 'Unexpected Echo release: %s\n' "$ECHO_RELEASE_VERSION" >&2
  exit 1
}

grep -Fq 'timeout --foreground 600' Echo_Linux_Installer.sh || exit 1
grep -Fq 'timeout --foreground 300' Echo_Linux_Installer.sh || exit 1
grep -Fq 'docker compose' Echo_Linux_Installer.sh || exit 1
grep -Fq 'setup_database' Echo_Linux_Installer.sh || exit 1
grep -Fq 'timeout=300' launcher.py || grep -Fq 'timeout=300,' launcher.py || grep -Fq 'timeout=300' launcher.py || exit 1
grep -Fq 'range(60)' launcher.py || exit 1
grep -Fq 'time.sleep(2)' launcher.py || exit 1
[[ "$VERSION" == "sentinel" ]] || {
  printf 'OS detection overwrote VERSION\n' >&2
  exit 1
}

ECHO_INSTALLER_TEST=1 source "$ROOT_DIR/Echo_Linux_Installer.sh"
check_linux
[[ "$INSTALL_ROOT" == "$HOME/.local/share/Echo" ]] || exit 1
[[ "$APP_DIR" == "$INSTALL_ROOT/Echo" ]] || exit 1
[[ "$APP_EXECUTABLE" == "$HOME/.local/share/Echo/Echo/Echo" ]] || exit 1
[[ "$APP_LAUNCHER" == "$HOME/.local/share/Echo/launch-echo.sh" ]] || exit 1

stale_variable="INSTALL""_DIR"
if grep -n "$stale_variable" install-echo.sh Echo_Linux_Installer.sh create-release-package.sh; then
  printf 'Stale installer path variable reference found\n' >&2
  exit 1
fi

printf 'Installer runtime test: OK\n'
printf '  ECHO_RELEASE_VERSION=%s\n' "$ECHO_RELEASE_VERSION"
printf '  INSTALL_ROOT=%s\n' "$INSTALL_ROOT"
printf '  APP_DIR=%s\n' "$APP_DIR"
printf '  APP_EXECUTABLE=%s\n' "$APP_EXECUTABLE"
