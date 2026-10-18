#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="Echo"
MODEL="qwen3:1.7b"
OLLAMA_MIN_VERSION="0.6.5"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTUAL_USER="${SUDO_USER:-$(id -un)}"
USER_HOME="$(getent passwd "$ACTUAL_USER" | cut -d: -f6)"
[[ -n "$USER_HOME" ]] || USER_HOME="$HOME"
INSTALL_ROOT="$USER_HOME/.local/share/Echo"
APP_DIR="$INSTALL_ROOT/Echo"
APP_EXECUTABLE="$APP_DIR/Echo"
LOG_DIR="$INSTALL_ROOT/logs"
DESKTOP_DIR="$USER_HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/echo.desktop"
ENV_FILE="$INSTALL_ROOT/.env"
DOCKER_GROUP_ADDED=0
OLLAMA_BIN=""

info() {
  printf '\n[Echo installer] %s\n' "$1"
}

fail() {
  printf '\n[Echo installer] ERROR: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

check_linux() {
  [[ "$(uname -s)" == "Linux" ]] || fail "Echo can only be installed on Linux."
  if [[ -r /etc/os-release ]]; then
    local os_id
    os_id="$(. /etc/os-release; printf '%s' "${ID:-}")"
    [[ "$os_id" == "ubuntu" ]] || fail "Echo is supported by this installer on Ubuntu only."
  else
    fail "Cannot identify the Linux distribution."
  fi
}

check_internet() {
  info "Checking internet connection"
  require_command curl
  curl --fail --silent --show-error --head --max-time 15 https://ollama.com >/dev/null \
    || fail "No usable internet connection was found."
}

check_sudo() {
  info "Checking sudo access"
  require_command sudo
  sudo -v || fail "Sudo access is required to install system packages."
}

install_system_packages() {
  if command -v curl >/dev/null 2>&1 \
    && docker --version >/dev/null 2>&1 \
    && docker compose version >/dev/null 2>&1; then
    info "Required system tools are already installed; skipping apt"
    return
  fi

  info "Installing required system packages"
  sudo apt-get update
  if ! command -v curl >/dev/null 2>&1; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
  fi

  if docker --version >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    info "Docker and Docker Compose are already installed; skipping Docker package installation"
  elif docker --version >/dev/null 2>&1; then
    info "Docker is already installed; installing only Docker Compose"
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-v2
  else
    info "Docker is missing; installing Docker and Docker Compose"
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2
  fi
}

setup_docker() {
  info "Enabling and starting Docker"
  sudo systemctl enable --now docker
  systemctl is-active --quiet docker || fail "Docker service could not be started."

  if [[ " $(id -nG "$ACTUAL_USER") " != *" docker "* ]]; then
    sudo usermod -aG docker "$ACTUAL_USER"
    DOCKER_GROUP_ADDED=1
    printf '\nDocker group access was added for %s.\n' "$ACTUAL_USER"
    printf 'Log out and log back in before starting Echo so Docker can be accessed without sudo.\n'
  fi
}

install_ollama() {
  if find_ollama; then
    if ollama_version_supported; then
      info "Ollama is already installed ($OLLAMA_VERSION)"
      return
    fi
    info "Upgrading Ollama from ${OLLAMA_VERSION:-an unknown version} to a Qwen3-compatible release"
  else
    info "Installing Ollama"
  fi

  local install_script="$LOG_DIR/ollama-install.sh"
  local install_log="$LOG_DIR/ollama-install.log"
  if ! curl --fail --location --silent --show-error \
    --connect-timeout 15 --max-time 120 --retry 4 --retry-delay 3 --retry-all-errors \
    https://ollama.com/install.sh -o "$install_script" >"$install_log" 2>&1; then
    fail "Could not download the Ollama installer. See $install_log."
  fi
  [[ -s "$install_script" ]] || fail "The downloaded Ollama installer is empty. See $install_log."
  local installer_header
  installer_header="$(head -c 2 "$install_script")"
  [[ "$installer_header" == "#!" ]] || fail "The downloaded Ollama installer is not a shell script. See $install_log."

  local attempt install_status=1
  for ((attempt = 1; attempt <= 3; attempt++)); do
    info "Running Ollama installer (attempt $attempt of 3)"
    set +e
    sudo sh "$install_script" 2>&1 | tee -a "$install_log"
    install_status=${PIPESTATUS[0]}
    set -e
    [[ "$install_status" -eq 0 ]] && break
    if [[ "$attempt" -lt 3 ]]; then
      info "Ollama download failed; retrying in 5 seconds"
      sleep 5
    fi
  done
  [[ "$install_status" -eq 0 ]] || fail "Ollama installation failed after 3 attempts. See $install_log."

  export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/usr/local/lib/ollama:/opt/ollama/bin:$PATH"
  hash -r
  find_ollama || fail "Ollama installation completed, but no usable executable was found. See $install_log."
  ollama_version_supported || fail "Ollama $OLLAMA_VERSION was installed, but Echo requires Ollama $OLLAMA_MIN_VERSION or newer for $MODEL. See $install_log."
}

OLLAMA_VERSION=""

ollama_version_supported() {
  [[ -n "$OLLAMA_VERSION" ]] \
    && [[ "$(printf '%s\n%s\n' "$OLLAMA_MIN_VERSION" "$OLLAMA_VERSION" | sort -V | head -n 1)" == "$OLLAMA_MIN_VERSION" ]]
}

find_ollama() {
  local candidate
  candidate="$(command -v ollama 2>/dev/null || true)"
  for candidate in "$candidate" "$HOME/.local/bin/ollama" /usr/local/bin/ollama /usr/bin/ollama \
    /usr/local/lib/ollama/ollama /opt/ollama/bin/ollama; do
    if [[ -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
      OLLAMA_BIN="$candidate"
      OLLAMA_VERSION="$($candidate --version | sed -nE 's/.*([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' | head -n 1)"
      return 0
    fi
  done
  return 1
}

wait_for_ollama() {
  local attempts=30
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error --max-time 2 \
      http://127.0.0.1:11434/api/tags >/dev/null 2>>"$LOG_DIR/ollama.log"; then
      return 0
    fi
    sleep 1
  done
  fail "Ollama did not become ready at http://127.0.0.1:11434/api/tags. Check $LOG_DIR/ollama.log."
}

start_ollama() {
  if command -v systemctl >/dev/null 2>&1 && systemctl cat ollama.service >/dev/null 2>&1; then
    info "Starting Ollama system service"
    sudo systemctl enable --now ollama \
      || fail "The Ollama system service could not be started. Check systemctl status ollama."
  else
    info "Starting Ollama"
    nohup "$OLLAMA_BIN" serve >>"$LOG_DIR/ollama.log" 2>&1 &
  fi
  wait_for_ollama
}

setup_model() {
  start_ollama
  local installed_models
  installed_models="$("$OLLAMA_BIN" list | awk 'NR > 1 { print $1 }')"
  if grep -Fxq "$MODEL" <<<"$installed_models"; then
    info "Ollama model $MODEL is already installed"
    return
  fi

  info "Downloading Ollama model $MODEL"
  "$OLLAMA_BIN" pull "$MODEL"
}

install_echo() {
  [[ -d "$SOURCE_DIR/dist/Echo" ]] || fail "PyInstaller directory not found at $SOURCE_DIR/dist/Echo."
  [[ -f "$SOURCE_DIR/dist/Echo/Echo" ]] || fail "Echo executable not found at $SOURCE_DIR/dist/Echo/Echo."
  [[ -x "$SOURCE_DIR/dist/Echo/Echo" ]] || fail "$SOURCE_DIR/dist/Echo/Echo is not executable."
  [[ -f "$SOURCE_DIR/docker-compose.yml" ]] || fail "docker-compose.yml was not found."
  [[ -d "$SOURCE_DIR/migrations" ]] || fail "Database migrations were not found."
  [[ -d "$SOURCE_DIR/assets" ]] || fail "Application assets were not found."
  [[ -f "$SOURCE_DIR/.env.example" ]] || fail ".env.example was not found."

  info "Installing Echo into $APP_DIR"
  mkdir -p "$INSTALL_ROOT" "$LOG_DIR" "$DESKTOP_DIR"
  local staged_app="$INSTALL_ROOT/.Echo.new.$$"
  rm -rf "$staged_app"
  cp -a "$SOURCE_DIR/dist/Echo" "$staged_app"
  [[ -f "$staged_app/Echo" && -x "$staged_app/Echo" ]] || fail "Staged Echo executable is invalid."
  rm -rf "$APP_DIR"
  mv "$staged_app" "$APP_DIR"

  install -m 644 "$SOURCE_DIR/docker-compose.yml" "$INSTALL_ROOT/docker-compose.yml"
  rm -rf "$INSTALL_ROOT/migrations" "$INSTALL_ROOT/assets"
  cp -a "$SOURCE_DIR/migrations" "$INSTALL_ROOT/migrations"
  cp -a "$SOURCE_DIR/assets" "$INSTALL_ROOT/assets"
  [[ -f "$INSTALL_ROOT/assets/icon.svg" ]] || fail "Installed Echo icon was not found."
  if [[ ! -f "$ENV_FILE" ]]; then
    install -m 600 "$SOURCE_DIR/.env.example" "$ENV_FILE"
    local db_password
    db_password="$(openssl rand -hex 32)"
    sed -i \
      -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$db_password/" \
      -e "s#^DATABASE_URL=.*#DATABASE_URL=postgresql://teamreport:$db_password@localhost:5432/teamreport#" \
      "$ENV_FILE"
  fi
  [[ -f "$APP_EXECUTABLE" && -x "$APP_EXECUTABLE" ]] || fail "Installed Echo executable was not found at $APP_EXECUTABLE."
}

create_desktop_entry() {
  info "Creating desktop launcher"
  cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Echo
Comment=AI-assisted daily team reporting
Exec=$APP_EXECUTABLE
Terminal=false
Icon=$INSTALL_ROOT/assets/icon.svg
Categories=Office;Utility;
EOF
  chmod 644 "$DESKTOP_FILE"
  [[ -x "$APP_EXECUTABLE" ]] || fail "Desktop launcher target does not exist: $APP_EXECUTABLE"
  [[ -f "$INSTALL_ROOT/assets/icon.svg" ]] || fail "Desktop launcher icon does not exist: $INSTALL_ROOT/assets/icon.svg"
  if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP_FILE" || fail "Desktop launcher validation failed."
  fi
}

main() {
  check_linux
  check_internet
  check_sudo
  require_command openssl
  install_system_packages
  setup_docker
  mkdir -p "$INSTALL_ROOT" "$LOG_DIR"
  install_ollama
  setup_model
  install_echo
  create_desktop_entry

  printf '\nEcho installation completed.\n'
  printf 'Open Echo from applications menu or run %s\n' "$APP_EXECUTABLE"
  if [[ "$DOCKER_GROUP_ADDED" == "1" ]]; then
    printf 'Important: log out and log back in before starting Echo so Docker group access takes effect.\n'
  fi
}

if [[ "${ECHO_INSTALLER_TEST:-0}" != "1" ]]; then
  main "$@"
fi