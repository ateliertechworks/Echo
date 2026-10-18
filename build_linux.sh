#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

command -v "$PY" >/dev/null 2>&1 || { echo "Python 3 is required" >&2; exit 1; }

"$PY" -m PyInstaller --noconfirm --clean --onefile --windowed --name Echo \
  --add-data "echo_app/assets:echo_app/assets" \
  --add-data "echo_app/db/migrations:echo_app/db/migrations" \
  --add-data "docker-compose.yml:." \
  launcher.py

echo "Built dist/Echo. The executable is ready to place in a later AppImage bundle."