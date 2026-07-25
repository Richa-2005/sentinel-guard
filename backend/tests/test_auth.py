"""Integration tests for registration, tokens, and two-role authorization."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="sentinel-auth-tests-")
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
db_path = Path(TEST_DIRECTORY.name) / "authentication.db"
os.environ["SENTINEL_DATABASE_PATH"] = str(db_path)
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-with-at-least-32-characters"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import jwt  # noqa: E402
from jwt.exceptions import InvalidTokenError  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.database import initialize_database  # noqa: E402
from app.core.security import (  # noqa: E402
    TOKEN_AUDIENCE,
    TOKEN_ISSUER,
    decode_access_token,
)
from app.models.user import Roles, User  # noqa: E402
from app.routers.auth import router as auth_router  # noqa: E402
from app.services.auth_service import create_user  # noqa: E402


db = initialize_database(db_path)

def override_get_db_conn():
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA synchronous=NORMAL;")
        connection.execute("PRAGMA foreign_keys=ON;")
        connection.execute("PRAGMA busy_timeout=30000;")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

from app.core.auth_dependencies import get_db_conn
test_app = FastAPI()
test_app.include_router(auth_router)
test_app.dependency_overrides[get_db_conn] = override_get_db_conn


class AuthenticationIntegrationTests(unittest.TestCase):
    """Exercise authentication through the public HTTP contracts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(test_app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        with db.connection() as conn:
            # Other integration modules may seed immutable review history in the
            # same process. Remove only users that are not referenced by it.
            conn.execute(
                """
                DELETE FROM users
                WHERE id NOT IN (
                    SELECT actor_user_id FROM review_actions
                    WHERE actor_user_id IS NOT NULL
                )
                AND id NOT IN (
                    SELECT assigned_to_user_id FROM review_cases
                    WHERE assigned_to_user_id IS NOT NULL
                )
                """
            )

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
        analyst = self.register_analyst()
        token = self.login("analyst@example.com")["access_token"]
        response = self.client.get(
            "/api/v1/auth/me",
            headers=self.authorization(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["email"], "analyst@example.com")
        self.assertEqual(payload["id"], analyst["id"])
        self.assertEqual(payload["role"], "analyst")

    def test_registration_rules_and_invalid_inputs(self) -> None:
        conflict = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "analyst@example.com",
                "full_name": "Test Analyst",
                "password": "correct-password",
            },
        )
        self.assertEqual(conflict.status_code, 201)

        repeated = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "analyst@example.com",
                "full_name": "Repeated Email",
                "password": "correct-password",
            },
        )
        self.assertEqual(repeated.status_code, 409)

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

        with db.connection() as conn:
            admin = create_user(
                conn,
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
        returned_emails = {user["email"] for user in users.json()}
        self.assertTrue({"analyst@example.com", "admin@example.com"} <= returned_emails)

        promoted = self.client.patch(
            f"/api/v1/auth/users/{analyst['id']}/role",
            json={"role": "admin"},
            headers=self.authorization(admin_token),
        )
        self.assertEqual(promoted.status_code, 404)

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
