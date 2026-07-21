"""Password hashing and signed access-token utilities."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.config import settings


TOKEN_ISSUER = "sentinel-guard"
TOKEN_AUDIENCE = "sentinel-guard-api"
TOKEN_TYPE = "access"

password_hasher = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password with the recommended Argon2 settings."""
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Return whether a password matches, including for unknown hashes."""
    try:
        return password_hasher.verify(plain_password, stored_hash)
    except UnknownHashError:
        return False


def _jwt_secret() -> str:
    """Return a sufficiently strong signing secret or fail securely."""
    if settings.JWT_SECRET_KEY is None:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    secret = settings.JWT_SECRET_KEY.get_secret_value()
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")
    return secret


def validate_auth_configuration() -> None:
    """Fail application startup when token signing is not configured safely."""
    _jwt_secret()


def create_access_token(user_id: int) -> tuple[str, int]:
    """Create a short-lived access token for one database user."""
    now = datetime.now(timezone.utc)
    lifetime = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": TOKEN_TYPE,
        "iat": now,
        "exp": now + lifetime,
        "jti": str(uuid4()),
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
    }
    token = jwt.encode(
        payload,
        _jwt_secret(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> int:
    """Validate an access token and return its positive integer user ID."""
    payload = jwt.decode(
        token,
        _jwt_secret(),
        algorithms=[settings.JWT_ALGORITHM],
        audience=TOKEN_AUDIENCE,
        issuer=TOKEN_ISSUER,
        options={
            "require": ["sub", "type", "iat", "exp", "jti", "iss", "aud"],
        },
    )

    if payload.get("type") != TOKEN_TYPE:
        raise InvalidTokenError("Token is not an access token")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Token subject is invalid") from exc

    if user_id <= 0:
        raise InvalidTokenError("Token subject is invalid")
    return user_id
