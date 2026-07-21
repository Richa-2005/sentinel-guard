"""Database operations for authentication and user administration."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import Roles, User


class UserAlreadyExistsError(ValueError):
    """Raised when a normalized email is already registered."""


def normalize_email(email: str) -> str:
    """Return the canonical database representation of an email address."""
    return email.strip().lower()


def get_user_by_email(session: Session, email: str) -> User | None:
    """Find a user by normalized email."""
    statement = select(User).where(User.email == normalize_email(email))
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: int) -> User | None:
    """Find a user by primary key."""
    return session.get(User, user_id)


def create_user(
    session: Session,
    *,
    email: str,
    full_name: str,
    plain_password: str,
    role: Roles = Roles.ANALYST,
) -> User:
    """Create one user with a securely hashed password."""
    user = User(
        email=normalize_email(email),
        full_name=" ".join(full_name.split()),
        password_hash=hash_password(plain_password),
        role=role,
        is_active=True,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise UserAlreadyExistsError("An account with this email already exists") from exc

    session.refresh(user)
    return user


def authenticate_user(
    session: Session,
    *,
    email: str,
    plain_password: str,
) -> User | None:
    """Return a user only when the supplied credentials are valid."""
    user = get_user_by_email(session, email)
    if user is None:
        return None
    if not verify_password(plain_password, user.password_hash):
        return None
    return user


def list_users(session: Session) -> list[User]:
    """Return users in stable creation order for the admin interface."""
    return list(session.scalars(select(User).order_by(User.id)))


def set_user_role(session: Session, user: User, role: Roles) -> User:
    """Persist an administrator-approved role change."""
    user.role = role
    session.commit()
    session.refresh(user)
    return user


def set_user_active_status(session: Session, user: User, is_active: bool) -> User:
    """Enable or disable a user without deleting audit-relevant identity."""
    user.is_active = is_active
    session.commit()
    session.refresh(user)
    return user
