"""Previous-report memory for the chatbot, used to resolve phrases like
"same project" or "previous work". Read-only."""

import logging
from datetime import date

from echo_app import db

log = logging.getLogger(__name__)


def empty_memory() -> dict:
    return {"lastProject": "", "lastWorkDone": "", "lastPending": ""}


def get_chat_memory(user_id, team_id, today: date | None = None) -> dict:
    """Latest saved report for this user/team before today; empty if none or the DB fails."""
    if not user_id or not team_id:
        return empty_memory()
    try:
        r = db.fetch_one(
            """SELECT project_name, work_done, leader_work, pending_work, next_plan
               FROM reports
               WHERE user_id = %s AND team_id = %s AND report_date < %s
               ORDER BY report_date DESC, submitted_time DESC
               LIMIT 1""",
            (user_id, team_id, today or date.today()),
        )
    except Exception as e:  # noqa: BLE001 — memory is best-effort
        log.warning("[chat-memory] falling back to empty memory: %s", e)
        return empty_memory()
    if not r:
        return empty_memory()
    return {
        "lastProject": r["project_name"] or "",
        "lastWorkDone": r["leader_work"] or r["work_done"] or "",
        "lastPending": " ".join(p for p in (r["pending_work"], r["next_plan"]) if p),
    }
