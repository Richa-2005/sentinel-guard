"""Integration tests for registration, tokens, and two-role authorization."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="sentinel-auth-tests-")
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
os.environ["SENTINEL_DATABASE_PATH"] = str(
    Path(TEST_DIRECTORY.name) / "authentication.db"
)
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-with-at-least-32-characters"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import jwt  # noqa: E402
from jwt.exceptions import InvalidTokenError  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.db_session import SessionLocal  # noqa: E402
from app.core.security import (  # noqa: E402
    TOKEN_AUDIENCE,
    TOKEN_ISSUER,
    decode_access_token,
)
from app.models.user import Roles, User  # noqa: E402
from app.routers.auth import router as auth_router  # noqa: E402
from app.services.auth_service import create_user  # noqa: E402


alembic_config = Config(str(BACKEND_DIRECTORY / "alembic.ini"))
command.upgrade(alembic_config, "head")

test_app = FastAPI()
test_app.include_router(auth_router)


class AuthenticationIntegrationTests(unittest.TestCase):
    """Exercise authentication through the public HTTP contracts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(test_app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        with SessionLocal() as session:
            session.execute(delete(User))
            session.commit()

    def register_analyst(self, email: str = "analyst@example.com") -> dict:
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "Test Analyst",
                "password": "correct-password",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def login(self, email: str, password: str = "correct-password") -> dict:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    @staticmethod
    def authorization(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_registration_login_and_current_user(self) -> None:
        registered = self.register_analyst("  Analyst@Example.com ")
        self.assertEqual(registered["email"], "analyst@example.com")
        self.assertEqual(registered["role"], "analyst")
        self.assertNotIn("password", registered)
        self.assertNotIn("password_hash", registered)

        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "ANALYST@example.com",
                "full_name": "Duplicate Analyst",
                "password": "another-password",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

        invalid_login = self.client.post(
            "/api/v1/auth/login",
            json={"email": "analyst@example.com", "password": "wrong"},
        )
        self.assertEqual(invalid_login.status_code, 401)

        token_response = self.login("ANALYST@example.com")
        self.assertEqual(token_response["token_type"], "bearer")
        self.assertEqual(token_response["expires_in"], 1800)

        current = self.client.get(
            "/api/v1/auth/me",
            headers=self.authorization(token_response["access_token"]),
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["email"], "analyst@example.com")

    def test_public_registration_cannot_choose_role(self) -> None:
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "attacker@example.com",
                "full_name": "Privilege Attempt",
                "password": "correct-password",
                "role": "admin",
            },
        )
        self.assertEqual(response.status_code, 422)

        short_password = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "valid@example.com",
                "full_name": "Valid Name",
                "password": "short",
            },
        )
        self.assertEqual(short_password.status_code, 422)

        invalid_email = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "full_name": "Valid Name",
                "password": "correct-password",
            },
        )
        self.assertEqual(invalid_email.status_code, 422)

    def test_admin_authorization_and_account_status(self) -> None:
        analyst = self.register_analyst()
        analyst_token = self.login("analyst@example.com")["access_token"]

        with SessionLocal() as session:
            admin = create_user(
                session,
                email="admin@example.com",
                full_name="Test Admin",
                plain_password="admin-password",
                role=Roles.ADMIN,
            )
            admin_id = admin.id

        admin_token = self.login("admin@example.com", "admin-password")[
            "access_token"
        ]

        forbidden = self.client.get(
            "/api/v1/auth/users",
            headers=self.authorization(analyst_token),
        )
        self.assertEqual(forbidden.status_code, 403)

        users = self.client.get(
            "/api/v1/auth/users",
            headers=self.authorization(admin_token),
        )
        self.assertEqual(users.status_code, 200)
        self.assertEqual(len(users.json()), 2)

        promoted = self.client.patch(
            f"/api/v1/auth/users/{analyst['id']}/role",
            json={"role": "admin"},
            headers=self.authorization(admin_token),
        )
        self.assertEqual(promoted.status_code, 200)
        self.assertEqual(promoted.json()["role"], "admin")

        self_demotion = self.client.patch(
            f"/api/v1/auth/users/{admin_id}/role",
            json={"role": "analyst"},
            headers=self.authorization(admin_token),
        )
        self.assertEqual(self_demotion.status_code, 400)

        disabled = self.client.patch(
            f"/api/v1/auth/users/{analyst['id']}/status",
            json={"is_active": False},
            headers=self.authorization(admin_token),
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["is_active"])

        disabled_request = self.client.get(
            "/api/v1/auth/me",
            headers=self.authorization(analyst_token),
        )
        self.assertEqual(disabled_request.status_code, 403)

    def test_missing_and_malformed_tokens_are_rejected(self) -> None:
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        response = self.client.get(
            "/api/v1/auth/me",
            headers=self.authorization("not-a-jwt"),
        )
        self.assertEqual(response.status_code, 401)

    def test_expired_and_wrong_type_tokens_are_rejected(self) -> None:
        secret = settings.JWT_SECRET_KEY.get_secret_value()
        now = datetime.now(timezone.utc)
        base_payload = {
            "sub": "1",
            "type": "access",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "jti": "expired-token-test",
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
        }
        expired = jwt.encode(base_payload, secret, algorithm="HS256")
        with self.assertRaises(InvalidTokenError):
            decode_access_token(expired)

        base_payload["exp"] = now + timedelta(minutes=1)
        base_payload["type"] = "refresh"
        wrong_type = jwt.encode(base_payload, secret, algorithm="HS256")
        with self.assertRaises(InvalidTokenError):
            decode_access_token(wrong_type)


if __name__ == "__main__":
    unittest.main()
