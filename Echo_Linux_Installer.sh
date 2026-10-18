#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Echo"
MODEL="qwen3:1.7b"
OLLAMA_MIN_VERSION="0.6.5"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/Echo"
LOG_DIR="$INSTALL_DIR/logs"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/echo.desktop"
EXECUTABLE="$INSTALL_DIR/Echo"
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
    # shellcheck disable=SC1091
    . /etc/os-release
    [[ "${ID:-}" == "ubuntu" ]] || fail "Echo is supported by this installer on Ubuntu only."
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

  if [[ " $(id -nG "$USER") " != *" docker "* ]]; then
    sudo usermod -aG docker "$USER"
    DOCKER_GROUP_ADDED=1
    printf '\nDocker group access was added for %s.\n' "$USER"
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
  [[ -f "$SOURCE_DIR/dist/Echo" ]] || fail "Built executable not found at $SOURCE_DIR/dist/Echo."
  [[ -x "$SOURCE_DIR/dist/Echo" ]] || fail "$SOURCE_DIR/dist/Echo is not executable."
  [[ -f "$SOURCE_DIR/docker-compose.yml" ]] || fail "docker-compose.yml was not found."
  [[ -d "$SOURCE_DIR/echo_app/db/migrations" ]] || fail "Database migrations were not found."

  info "Installing Echo into $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR" "$LOG_DIR" "$DESKTOP_DIR"
  install -m 755 "$SOURCE_DIR/dist/Echo" "$EXECUTABLE"
  install -m 644 "$SOURCE_DIR/docker-compose.yml" "$INSTALL_DIR/docker-compose.yml"
  rm -rf "$INSTALL_DIR/migrations" "$INSTALL_DIR/assets"
  cp -a "$SOURCE_DIR/echo_app/db/migrations" "$INSTALL_DIR/migrations"
  if [[ -d "$SOURCE_DIR/echo_app/assets" ]]; then
    cp -a "$SOURCE_DIR/echo_app/assets" "$INSTALL_DIR/assets"
  fi
  if [[ -f "$SOURCE_DIR/.env.example" ]]; then
    install -m 644 "$SOURCE_DIR/.env.example" "$INSTALL_DIR/.env.example"
  fi
}

create_desktop_entry() {
  info "Creating desktop launcher"
  cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Echo
Comment=AI-assisted daily team reporting
Exec=$EXECUTABLE
Terminal=false
Categories=Office;Utility;
EOF
  chmod 644 "$DESKTOP_FILE"
}

main() {
  check_linux
  check_internet
  check_sudo
  install_system_packages
  setup_docker
  mkdir -p "$INSTALL_DIR" "$LOG_DIR"
  install_ollama
  setup_model
  install_echo
  create_desktop_entry

  printf '\nEcho installation completed.\n'
  printf 'Open Echo from applications menu or run %s\n' "$EXECUTABLE"
  if [[ "$DOCKER_GROUP_ADDED" == "1" ]]; then
    printf 'Important: log out and log back in before starting Echo so Docker group access takes effect.\n'
  fi
}

main "$@"