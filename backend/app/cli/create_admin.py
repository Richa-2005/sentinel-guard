"""Interactively create the first Sentinel Guard administrator."""

import argparse
from getpass import getpass

from pydantic import ValidationError

from app.core.db_session import SessionLocal
from app.models.user import Roles
from app.schemas.auth import UserRegister
from app.services.auth_service import UserAlreadyExistsError, create_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an active Sentinel Guard administrator.",
    )
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--name", required=True, help="Administrator display name")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 1

    try:
        payload = UserRegister(
            email=args.email,
            full_name=args.name,
            password=password,
        )
    except ValidationError as exc:
        print(exc)
        return 1

    with SessionLocal() as session:
        try:
            user = create_user(
                session,
                email=str(payload.email),
                full_name=payload.full_name,
                plain_password=payload.password.get_secret_value(),
                role=Roles.ADMIN,
            )
        except UserAlreadyExistsError as exc:
            print(str(exc))
            return 1

    print(f"Created administrator {user.email} (id={user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
