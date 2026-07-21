"""Password hashing utilities for authentication."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


ph = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    
    return ph.hash(plain_password)


def verify_password(plain_password: str, stored_hash: str) -> bool:
    
    try:
        return ph.verify(plain_password, stored_hash)
    except UnknownHashError:
        return False
