import json
from datetime import date

from echo_app import db
from echo_app.services import ServiceError
from echo_app.services.teams import require_role


def date_filter_clauses(alias: str, filters: dict) -> tuple[list[str], list]:
    """SQL clauses for the optional project/date/from/to/month/year filters on `alias.*`."""
    clauses, params = [], []

    def add(clause, value):
        clauses.append(clause)
        params.append(value)

    if filters.get("project"):
        add(f"{alias}.project_name ILIKE %s", f"%{filters['project']}%")
    if filters.get("date"):
        add(f"{alias}.report_date = %s", filters["date"])
    if filters.get("from"):
        add(f"{alias}.report_date >= %s", filters["from"])
    if filters.get("to"):
        add(f"{alias}.report_date <= %s", filters["to"])
    if filters.get("month"):
        add(f"EXTRACT(MONTH FROM {alias}.report_date) = %s", int(filters["month"]))
    if filters.get("year"):
        add(f"EXTRACT(YEAR FROM {alias}.report_date) = %s", int(filters["year"]))
    return clauses, params


def list_reports(team_id, user_id, filters: dict | None = None) -> list[dict]:
    """Saved reports for a team. Members only ever see their own rows."""
    filters = filters or {}
    role = require_role(team_id, user_id)
    clauses, params = ["r.team_id = %s"], [team_id]
    if role == "member":
        clauses.append("r.user_id = %s")
        params.append(user_id)
    elif filters.get("user_id"):
        clauses.append("r.user_id = %s")
        params.append(filters["user_id"])
    extra, extra_params = date_filter_clauses("r", filters)
    return db.fetch_all(
        f"""SELECT r.*, p.username, p.email
            FROM reports r
            JOIN profiles p ON p.id = r.user_id
            WHERE {' AND '.join(clauses + extra)}
            ORDER BY r.report_date DESC, r.submitted_time DESC""",
        params + extra_params,
    )


def save_report(user_id, team_id, structured: dict, report_date: date | None = None) -> dict:
    """Upserts today's report (one per user/team/day). Returns {'report', 'updated'}."""
    if not structured:
        raise ServiceError("Nothing to save yet")
    role = require_role(team_id, user_id)
    report_date = report_date or date.today()
    is_leader = role == "leader"
    s = lambda key: structured.get(key) or None  # noqa: E731

    with db.transaction() as conn:
        report = conn.execute(
            """INSERT INTO reports (user_id, team_id, project_name, work_done, leader_work, team_progress,
                                    outcome, blockers, pending_work, next_plan, chatbot_summary, report_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id, team_id, report_date)
               DO UPDATE SET
                 project_name    = EXCLUDED.project_name,
                 work_done       = EXCLUDED.work_done,
                 leader_work     = EXCLUDED.leader_work,
                 team_progress   = EXCLUDED.team_progress,
                 outcome         = EXCLUDED.outcome,
                 blockers        = EXCLUDED.blockers,
                 pending_work    = EXCLUDED.pending_work,
                 next_plan       = EXCLUDED.next_plan,
                 chatbot_summary = EXCLUDED.chatbot_summary,
                 submitted_time  = now(),
                 updated_at      = now()
               RETURNING *, (xmax = 0) AS inserted""",
            (
                user_id, team_id, s("project_name"),
                s("leader_work") if is_leader else s("work_done"),
                s("leader_work") if is_leader else None,
                s("team_progress") if is_leader else None,
                s("outcome"), s("blockers"), s("pending_work"), s("next_plan"), s("narrative"),
                report_date,
            ),
        ).fetchone()
        # The day's discussion mirrors the latest saved report: replaced when present,
        # removed when the re-saved report no longer has one.
        if is_leader and structured.get("team_discussion"):
            conn.execute(
                """INSERT INTO discussions (leader_id, team_id, project_name, discussion_summary, report_date)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (leader_id, team_id, report_date)
                   DO UPDATE SET
                     project_name       = EXCLUDED.project_name,
                     discussion_summary = EXCLUDED.discussion_summary,
                     submitted_time     = now(),
                     updated_at         = now()""",
                (user_id, team_id, s("project_name"), structured["team_discussion"], report_date),
            )
        elif is_leader:
            conn.execute(
                "DELETE FROM discussions WHERE leader_id = %s AND team_id = %s AND report_date = %s",
                (user_id, team_id, report_date),
            )
        # Keep the final structured summary for auditability.
        conn.execute(
            """INSERT INTO chat_messages (team_id, user_id, role, message, message_type, report_date)
               VALUES (%s,%s,%s,%s,'summary',%s)""",
            (team_id, user_id, role, json.dumps(structured, ensure_ascii=False), report_date),
        )
    inserted = report.pop("inserted")
    return {"report": report, "updated": not inserted}


def reset_today(user_id, team_id, report_date: date | None = None):
    """Clears only the day's draft conversation; the saved report is untouched."""
    require_role(team_id, user_id)
    db.execute(
        "DELETE FROM chat_messages WHERE team_id = %s AND user_id = %s AND report_date = %s",
        (team_id, user_id, report_date or date.today()),
    )
