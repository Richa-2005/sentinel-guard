"""Request and response contracts for authentication APIs."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)

from app.models.user import Roles


class NormalizedEmailModel(BaseModel):
    """Normalize email identities consistently before database queries."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserRegister(NormalizedEmailModel):
    """Public registration input; role is deliberately not accepted."""

    full_name: str = Field(min_length=2, max_length=150)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("full_name", mode="after")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("full_name must contain at least 2 characters")
        return normalized


class LoginRequest(NormalizedEmailModel):
    """Credentials accepted by the login endpoint."""

    password: SecretStr = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Safe public user representation without credential material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: Roles
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Bearer token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserRoleUpdate(BaseModel):
    """Administrator request for changing a user's role."""

    model_config = ConfigDict(extra="forbid")

    role: Roles


class UserStatusUpdate(BaseModel):
    """Administrator request for enabling or disabling a user."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool
