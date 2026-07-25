"""Integration coverage for the explicitly gated portfolio demo entry."""

import os
import tempfile
import unittest
from pathlib import Path


TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="sentinel-demo-tests-")
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
os.environ["SENTINEL_DATABASE_PATH"] = str(Path(TEST_DIRECTORY.name) / "demo.db")
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-with-at-least-32-characters"
os.environ["DEMO_MODE"] = "true"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.db_session import SessionLocal  # noqa: E402
from app.routers.auth import router as auth_router  # noqa: E402


alembic_config = Config(str(BACKEND_DIRECTORY / "alembic.ini"))
command.upgrade(alembic_config, "head")
test_app = FastAPI()
test_app.include_router(auth_router)


class DemoAuthenticationTests(unittest.TestCase):
    def test_role_entries_are_idempotent_and_seed_useful_data(self) -> None:
        previous_demo_mode = settings.DEMO_MODE
        try:
            with TestClient(test_app) as client:
                settings.DEMO_MODE = False
                disabled = client.post("/api/v1/auth/demo", json={"role": "analyst"})

                settings.DEMO_MODE = True
                analyst = client.post("/api/v1/auth/demo", json={"role": "analyst"})
                admin = client.post("/api/v1/auth/demo", json={"role": "admin"})
                repeated = client.post("/api/v1/auth/demo", json={"role": "analyst"})
                password_login = client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "demo.analyst@sentinelguard.dev",
                        "password": "demo-account-not-for-password-login",
                    },
                )
        finally:
            settings.DEMO_MODE = previous_demo_mode

        self.assertEqual(disabled.status_code, 404, disabled.text)
        self.assertEqual(analyst.status_code, 200, analyst.text)
        self.assertEqual(admin.status_code, 200, admin.text)
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(password_login.status_code, 401, password_login.text)
        self.assertEqual(analyst.json()["user"]["role"], "analyst")
        self.assertEqual(admin.json()["user"]["role"], "admin")

        with SessionLocal() as session:
            self.assertEqual(
                session.scalar(
                    text(
                        "SELECT COUNT(*) FROM users "
                        "WHERE email LIKE 'demo.%@sentinelguard.dev'"
                    )
                ),
                2,
            )
            self.assertEqual(session.scalar(text("SELECT COUNT(*) FROM transactions_ledger WHERE transaction_id LIKE 'demo-v2-%'")), 72)
            refreshed_windows = session.execute(text("""
                SELECT
                    SUM(CASE WHEN datetime(timestamp) >= datetime('now', '-24 hours') THEN 1 ELSE 0 END) AS current_count,
                    SUM(CASE WHEN datetime(timestamp) < datetime('now', '-24 hours')
                              AND datetime(timestamp) >= datetime('now', '-48 hours') THEN 1 ELSE 0 END) AS previous_count
                FROM transactions_ledger
                WHERE transaction_id LIKE 'demo-v2-%'
            """)).mappings().one()
            self.assertGreaterEqual(refreshed_windows["current_count"], 30)
            self.assertGreaterEqual(refreshed_windows["previous_count"], 30)
            self.assertEqual(session.scalar(text("SELECT COUNT(*) FROM review_cases WHERE transaction_id LIKE 'demo-v2-%'")), 6)
            self.assertEqual(session.scalar(text("SELECT COUNT(*) FROM audit_vault WHERE transaction_id LIKE 'demo-v2-%'")), 5)
            shortest_report = session.scalar(text("SELECT MIN(length(compliance_memo)) FROM audit_vault WHERE transaction_id LIKE 'demo-v2-%'"))
            self.assertGreater(shortest_report, 1000)


if __name__ == "__main__":
    unittest.main()
