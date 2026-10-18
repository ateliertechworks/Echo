"""Runtime settings, read from environment variables or a `.env` file.

`.env` is looked up next to the packaged executable, in the current directory,
and in the project root (first match wins per variable).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
ASSETS_DIR = PACKAGE_DIR / "assets"
MIGRATIONS_DIR = PACKAGE_DIR / "db" / "migrations"
DATA_DIR = Path(os.getenv("ECHO_DATA_DIR", Path.home() / ".local" / "share" / "Echo"))
LOG_DIR = DATA_DIR / "logs"

for candidate in (DATA_DIR / ".env", Path(sys.executable).parent / ".env", Path.cwd() / ".env", PROJECT_ROOT / ".env"):
    if candidate.is_file():
        load_dotenv(candidate, override=False)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://teamreport:change-me-strong@localhost:5432/teamreport"
)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_MS", "60000")) / 1000
