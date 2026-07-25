import sqlite3
from app.core.security import hash_password, verify_password
from app.models.user import Roles, User

class UserAlreadyExistsError(ValueError):
    pass

def normalize_email(email: str) -> str:
    return email.strip().lower()

def _row_to_user(row) -> User | None:
    if not row:
        return None
    return User(
        id=row["id"], email=row["email"], full_name=row["full_name"],
        password_hash=row["password_hash"], role=Roles(row["role"]),
        is_active=bool(row["is_active"]), created_at=row["created_at"], updated_at=row["updated_at"]
    )

def get_user_by_email(conn: sqlite3.Connection, email: str) -> User | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
    return _row_to_user(row)

def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row)

def create_user(conn: sqlite3.Connection, *, email: str, full_name: str, plain_password: str, role: Roles = Roles.ANALYST) -> User:
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, 1)",
            (normalize_email(email), " ".join(full_name.split()), hash_password(plain_password), role.value)
        )
        return get_user_by_id(conn, cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise UserAlreadyExistsError("An account with this email already exists") from exc

def authenticate_user(conn: sqlite3.Connection, *, email: str, plain_password: str) -> User | None:
    user = get_user_by_email(conn, email)
    if user and verify_password(plain_password, user.password_hash):
        return user
    return None

def list_users(conn: sqlite3.Connection) -> list[User]:
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [_row_to_user(r) for r in rows]

def set_user_role(conn: sqlite3.Connection, user: User, role: Roles) -> User:
    conn.execute("UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (role.value, user.id))
    return get_user_by_id(conn, user.id)

def set_user_active_status(conn: sqlite3.Connection, user: User, is_active: bool) -> User:
    conn.execute("UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (int(is_active), user.id))
    return get_user_by_id(conn, user.id)