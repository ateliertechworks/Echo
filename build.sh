#!/usr/bin/env bash
# Packages Echo as a standalone desktop app in dist/Echo/ (run on each target OS).
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

"$PY" -m pip install -q pyinstaller
"$PY" -m PyInstaller --noconfirm --clean --windowed --name Echo \
  --add-data "echo_app/assets:echo_app/assets" \
  --add-data "echo_app/db/migrations:echo_app/db/migrations" \
  main.py

echo "Built dist/Echo/ — put a .env next to the Echo executable to point it at your database."
