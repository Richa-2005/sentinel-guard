import enum
from dataclasses import dataclass

class Roles(str, enum.Enum):
    ANALYST = "analyst"
    ADMIN = "admin"

@dataclass
class User:
    id: int
    email: str
    full_name: str
    password_hash: str
    role: Roles
    is_active: bool
    created_at: str
    updated_at: str