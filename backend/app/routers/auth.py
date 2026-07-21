"""Authentication and two-role user administration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import AdminUser, CurrentUser
from app.core.db_session import get_db
from app.core.security import create_access_token
from app.models.user import Roles
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.services.auth_service import (
    UserAlreadyExistsError,
    authenticate_user,
    create_user,
    get_user_by_id,
    list_users,
    set_user_active_status,
    set_user_role,
)


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(payload: UserRegister, session: DatabaseSession):
    """Register an active analyst account; public role selection is forbidden."""
    try:
        return create_user(
            session,
            email=str(payload.email),
            full_name=payload.full_name,
            plain_password=payload.password.get_secret_value(),
            role=Roles.ANALYST,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: DatabaseSession):
    """Authenticate credentials and issue a short-lived bearer token."""
    user = authenticate_user(
        session,
        email=str(payload.email),
        plain_password=payload.password.get_secret_value(),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    token, expires_in = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: CurrentUser):
    """Return the identity represented by the bearer token."""
    return current_user


@router.get("/users", response_model=list[UserResponse])
def read_users(_admin: AdminUser, session: DatabaseSession):
    """List accounts for the administrator dashboard."""
    return list_users(session)


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    admin: AdminUser,
    session: DatabaseSession,
):
    """Change an account role while preventing administrator self-demotion."""
    user = get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and payload.role is not Roles.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot demote their own account",
        )
    return set_user_role(session, user, payload.role)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    admin: AdminUser,
    session: DatabaseSession,
):
    """Enable or disable an account while preventing administrator lockout."""
    user = get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot disable their own account",
        )
    return set_user_active_status(session, user, payload.is_active)
