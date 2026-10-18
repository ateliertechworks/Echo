from psycopg import errors

from echo_app import db
from echo_app.services import ServiceError

PROFILE_FIELDS = """id, username, email, linkedin_url, github_url, kaggle_url, medium_url,
  profile_photo, role_title, bio, skills, profile_completed, created_at"""


def get_profile(user_id) -> dict:
    row = db.fetch_one(f"SELECT {PROFILE_FIELDS} FROM profiles WHERE id = %s", (user_id,))
    if not row:
        raise ServiceError("Profile not found")
    return row


def update_profile(user_id, data: dict) -> dict:
    username = (data.get("username") or "").strip() or None
    email = (data.get("email") or "").strip() or None
    skills = data.get("skills")
    try:
        return db.fetch_one(
            f"""UPDATE profiles SET
                  username = COALESCE(%s, username),
                  email = COALESCE(%s, email),
                  linkedin_url = %s,
                  github_url = %s,
                  kaggle_url = %s,
                  medium_url = %s,
                  profile_photo = %s,
                  role_title = %s,
                  bio = %s,
                  skills = %s,
                  profile_completed = TRUE
                WHERE id = %s
                RETURNING {PROFILE_FIELDS}""",
            (
                username,
                email,
                data.get("linkedin_url") or None,
                data.get("github_url") or None,
                data.get("kaggle_url") or None,
                data.get("medium_url") or None,
                data.get("profile_photo") or None,
                data.get("role_title") or None,
                data.get("bio") or None,
                list(skills) if isinstance(skills, (list, tuple)) else None,
                user_id,
            ),
        )
    except errors.UniqueViolation:
        raise ServiceError("That email is already used by another account") from None
