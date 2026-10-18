import bcrypt

from echo_app import db
from echo_app.services import ServiceError

USER_FIELDS = "id, username, email, profile_completed"


def _secret(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes (bcryptjs truncated silently; bcrypt>=5 raises).
    return password.encode("utf-8")[:72]


def signup(username: str, email: str, password: str) -> dict:
    username, email = (username or "").strip(), (email or "").strip()
    if not username or not email or not password:
        raise ServiceError("Username, email and password are required")
    if len(password) < 6:
        raise ServiceError("Password too short")
    if db.fetch_one("SELECT id FROM profiles WHERE email = %s", (email,)):
        raise ServiceError("Email already registered")
    password_hash = bcrypt.hashpw(_secret(password), bcrypt.gensalt(10)).decode()
    return db.fetch_one(
        f"""INSERT INTO profiles (username, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING {USER_FIELDS}""",
        (username, email, password_hash),
    )


def signin(email: str, password: str) -> dict:
    email = (email or "").strip()
    if not email or not password:
        raise ServiceError("Email and password are required")
    row = db.fetch_one(f"SELECT {USER_FIELDS}, password_hash FROM profiles WHERE email = %s", (email,))
    if not row or not bcrypt.checkpw(_secret(password), row["password_hash"].encode()):
        raise ServiceError("Invalid credentials")
    row.pop("password_hash")
    return row


def get_user(user_id) -> dict | None:
    return db.fetch_one(f"SELECT {USER_FIELDS} FROM profiles WHERE id = %s", (user_id,))
