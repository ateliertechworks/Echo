import secrets

from echo_app import db
from echo_app.services import ServiceError

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_code(length=8) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def get_role(team_id, user_id) -> str | None:
    row = db.fetch_one(
        "SELECT role FROM team_members WHERE team_id = %s AND user_id = %s", (team_id, user_id)
    )
    return row["role"] if row else None


def require_role(team_id, user_id) -> str:
    role = get_role(team_id, user_id)
    if not role:
        raise ServiceError("You are not a member of this team")
    return role


def create_team(user_id, team_name: str, description: str = "") -> dict:
    team_name = (team_name or "").strip()
    if not team_name:
        raise ServiceError("Team name is required")
    with db.transaction() as conn:
        code = _generate_code()
        for _ in range(5):
            if not conn.execute("SELECT 1 FROM teams WHERE team_code = %s", (code,)).fetchone():
                break
            code = _generate_code()
        team = conn.execute(
            """INSERT INTO teams (team_name, team_code, description, created_by)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (team_name, code, (description or "").strip() or None, user_id),
        ).fetchone()
        conn.execute(
            "INSERT INTO team_members (team_id, user_id, role) VALUES (%s, %s, 'leader')",
            (team["id"], user_id),
        )
    return {**team, "role": "leader"}


def join_team(user_id, team_code: str) -> dict:
    team_code = (team_code or "").strip().upper()
    if not team_code:
        raise ServiceError("Team code is required")
    team = db.fetch_one("SELECT * FROM teams WHERE team_code = %s", (team_code,))
    if not team:
        raise ServiceError("Team code not found")
    role = get_role(team["id"], user_id)
    if role:
        return {**team, "role": role}
    db.execute(
        "INSERT INTO team_members (team_id, user_id, role) VALUES (%s, %s, 'member')",
        (team["id"], user_id),
    )
    return {**team, "role": "member"}


def list_my_teams(user_id) -> list[dict]:
    return db.fetch_all(
        """SELECT t.*, tm.role,
                  (SELECT COUNT(*) FROM team_members WHERE team_id = t.id)::int AS member_count
           FROM teams t
           JOIN team_members tm ON tm.team_id = t.id
           WHERE tm.user_id = %s
           ORDER BY t.created_at DESC""",
        (user_id,),
    )


def get_team(team_id, user_id) -> dict:
    role = require_role(team_id, user_id)
    team = db.fetch_one("SELECT * FROM teams WHERE id = %s", (team_id,))
    if not team:
        raise ServiceError("Team not found")
    return {**team, "role": role}


def list_members(team_id, user_id) -> list[dict]:
    require_role(team_id, user_id)
    return db.fetch_all(
        """SELECT p.id, p.username, p.email, p.linkedin_url, p.github_url, p.kaggle_url, p.medium_url,
                  p.profile_photo, p.role_title, p.bio, p.skills, tm.role, tm.joined_at
           FROM team_members tm
           JOIN profiles p ON p.id = tm.user_id
           WHERE tm.team_id = %s
           ORDER BY (tm.role = 'leader') DESC, tm.joined_at ASC""",
        (team_id,),
    )


def remove_member(team_id, actor_id, member_id):
    if require_role(team_id, actor_id) != "leader":
        raise ServiceError("Only the team leader can remove members")
    target = get_role(team_id, member_id)
    if not target:
        raise ServiceError("Member not found")
    if target == "leader":
        raise ServiceError("Cannot remove the leader")
    db.execute("DELETE FROM team_members WHERE team_id = %s AND user_id = %s", (team_id, member_id))
