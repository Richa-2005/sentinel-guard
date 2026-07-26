import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth_dependencies import AdminUser, CurrentUser, DbConnection
from app.core.security import create_access_token, hash_password
from app.config import settings
from app.models.user import Roles
from app.schemas.auth import (
    LoginRequest,
    DemoLoginRequest,
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
    get_user_by_email,
    get_user_by_id,
    list_users,
    set_user_active_status,
    set_user_role,
)
from app.services.demo_service import ensure_demo_environment

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, conn: DbConnection):
    try:
        user = create_user(conn, email=str(payload.email), full_name=payload.full_name, plain_password=payload.password.get_secret_value(), role=Roles.ANALYST)
        return user.__dict__
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, conn: DbConnection):
    user = authenticate_user(conn, email=str(payload.email), plain_password=payload.password.get_secret_value())
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")

    token, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in, user=user.__dict__)

@router.post("/demo", response_model=TokenResponse)
def login_demo(payload: DemoLoginRequest, conn: DbConnection):
    """Issue a disposable role-specific session only in an explicit demo runtime."""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo access is disabled")

    identities = {
        Roles.ANALYST: ("demo.analyst@sentinelguard.dev", "Maya Chen"),
        Roles.ADMIN: ("demo.admin@sentinelguard.dev", "Arjun Mehta"),
    }
    demo_users = {}
    for role, (email, full_name) in identities.items():
        demo_user = get_user_by_email(conn, email)
        if demo_user is None:
            demo_user = create_user(
                conn,
                email=email,
                full_name=full_name,
                plain_password=secrets.token_urlsafe(48),
                role=role,
            )
        elif demo_user.role is not role:
            demo_user = set_user_role(conn, demo_user, role)
        if not demo_user.is_active:
            demo_user = set_user_active_status(conn, demo_user, True)
        
        # Demo identities are button-only. Setting a dummy invalid password hash
        # prevents the regular credential endpoint from becoming a backdoor without
        # incurring expensive CPU hashing costs.
        conn.execute("UPDATE users SET password_hash = 'demo_user_disabled_password' WHERE id = ?", (demo_user.id,))
        demo_users[role] = get_user_by_id(conn, demo_user.id)

    user = demo_users[payload.role]

    ensure_demo_environment(conn)
    token, expires_in = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=user.__dict__,
    )

@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: CurrentUser):
    return current_user.__dict__

@router.get("/users", response_model=list[UserResponse])
def read_users(_admin: AdminUser, conn: DbConnection):
    return [u.__dict__ for u in list_users(conn)]