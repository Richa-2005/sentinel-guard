import sqlite3
from typing import Annotated, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from app.core.database import SentinelDatabase, DEFAULT_DATABASE_PATH
from app.core.security import decode_access_token
from app.models.user import Roles, User
from app.services.auth_service import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)
db_manager = SentinelDatabase(DEFAULT_DATABASE_PATH)

def get_db_conn():
    with db_manager.connection() as conn:
        yield conn

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_conn)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

def _authentication_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing authentication credentials", headers={"WWW-Authenticate": "Bearer"})

def get_current_user(credentials: BearerCredentials, conn: DbConnection) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise _authentication_error() from exc

    user = get_user_by_id(conn, user_id)
    if user is None:
        raise _authentication_error()
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

def require_roles(*allowed_roles: Roles) -> Callable[..., User]:
    allowed = frozenset(allowed_roles)
    def role_dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return role_dependency

require_admin = require_roles(Roles.ADMIN)
AdminUser = Annotated[User, Depends(require_admin)]
require_analyst = require_roles(Roles.ANALYST)
AnalystUser = Annotated[User, Depends(require_analyst)]