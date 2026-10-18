"""The signed-in user, remembered between launches, plus per-day chat drafts on disk."""

import json
import logging
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

log = logging.getLogger(__name__)


class Session:
    def __init__(self):
        self.settings = QSettings()
        self.user: dict | None = None

    @property
    def user_id(self):
        return self.user["id"] if self.user else None

    def remembered_user_id(self) -> str | None:
        return self.settings.value("session/user_id") or None

    def sign_in(self, user: dict):
        self.user = dict(user)
        self.settings.setValue("session/user_id", str(user["id"]))

    def update(self, patch: dict):
        self.user = {**(self.user or {}), **patch}

    def sign_out(self):
        self.user = None
        self.settings.remove("session/user_id")


def _chat_dir() -> Path:
    path = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)) / "chat"
    path.mkdir(parents=True, exist_ok=True)
    return path


def chat_state_path(user_id, team_id, report_date) -> Path:
    return _chat_dir() / f"{user_id}_{team_id}_{report_date.isoformat()}.json"


def load_chat_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def store_chat_state(path: Path, state: dict):
    try:
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log.warning("Could not save chat draft: %s", e)


def drop_chat_state(path: Path):
    path.unlink(missing_ok=True)
