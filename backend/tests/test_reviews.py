"""Integration tests for the human-in-the-loop review state machine."""

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-key-with-at-least-32-characters",
)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.engine import URL  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.db_session import get_db  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.user import Roles  # noqa: E402
from app.routers.reviews import router as reviews_router  # noqa: E402
from app.services.auth_service import create_user  # noqa: E402
from app.services.review_service import (  # noqa: E402
    ensure_review_case_for_blocked_transaction,
)


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


class HumanReviewIntegrationTests(unittest.TestCase):
    """Exercise automatic cases, RBAC, transitions, and immutable history."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory(
            prefix="sentinel-review-tests-"
        )
        cls.database_path = Path(cls.temporary_directory.name) / "reviews.db"

        environment = os.environ.copy()
        environment["SENTINEL_DATABASE_PATH"] = str(cls.database_path)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(BACKEND_DIRECTORY / "alembic.ini"),
                "upgrade",
                "head",
            ],
            cwd=BACKEND_DIRECTORY,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

        cls.engine = create_engine(
            URL.create(drivername="sqlite", database=str(cls.database_path)),
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(cls.engine, "connect")
        def configure_sqlite(dbapi_connection, connection_record) -> None:
            del connection_record
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        cls.SessionLocal = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )

        def override_get_db():
            session = cls.SessionLocal()
            try:
                yield session
            finally:
                session.close()

        review_app = FastAPI()
        review_app.include_router(reviews_router)
        review_app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(review_app)

        with cls.SessionLocal() as session:
            cls.analyst = create_user(
                session,
                email="reviewer@example.com",
                full_name="Review Analyst",
                plain_password="analyst-password",
                role=Roles.ANALYST,
            )
            cls.other_analyst = create_user(
                session,
                email="other@example.com",
                full_name="Other Analyst",
                plain_password="analyst-password",
                role=Roles.ANALYST,
            )
            cls.admin = create_user(
                session,
                email="review-admin@example.com",
                full_name="Review Admin",
                plain_password="admin-password",
                role=Roles.ADMIN,
            )

        cls.analyst_headers = cls.authorization(cls.analyst.id)
        cls.other_headers = cls.authorization(cls.other_analyst.id)
        cls.admin_headers = cls.authorization(cls.admin.id)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.engine.dispose()
        cls.temporary_directory.cleanup()

    @staticmethod
    def authorization(user_id: int) -> dict[str, str]:
        token, _ = create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    @classmethod
    def create_blocked_case(cls, transaction_id: str, risk_score: float = 0.95) -> int:
        connection = sqlite3.connect(cls.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            connection.execute(
                """
                INSERT INTO transactions_ledger (
                    transaction_id,
                    card_id,
                    device_id,
                    merchant_id,
                    timestamp,
                    amount_paise,
                    ensemble_risk_score,
                    is_blocked,
                    hydrated_metrics,
                    shap_payload
                ) VALUES (?, 'card', 'device', 'merchant', ?, 50000, ?, 1, '{}', '{}')
                """,
                (transaction_id, "2026-07-21T00:00:00Z", risk_score),
            )
            first_id = ensure_review_case_for_blocked_transaction(
                connection,
                transaction_id=transaction_id,
                risk_score=risk_score,
            )
            second_id = ensure_review_case_for_blocked_transaction(
                connection,
                transaction_id=transaction_id,
                risk_score=risk_score,
            )
            connection.commit()
        finally:
            connection.close()
        if first_id != second_id:
            raise AssertionError("Idempotent review creation returned different cases")
        return first_id

    def test_automatic_case_is_idempotent_and_contains_model_context(self) -> None:
        case_id = self.create_blocked_case("review-context")
        response = self.client.get(
            f"/api/v1/reviews/{case_id}",
            headers=self.analyst_headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        self.assertEqual(detail["status"], "open")
        self.assertEqual(detail["priority"], "critical")
        self.assertEqual(detail["version"], 1)
        self.assertEqual(detail["transaction"]["ensemble_risk_score"], 0.95)
        self.assertTrue(detail["transaction"]["is_blocked"])
        self.assertEqual(len(detail["actions"]), 1)
        self.assertEqual(detail["actions"][0]["action_type"], "created")

    def test_claim_decide_conflict_and_immutable_history(self) -> None:
        case_id = self.create_blocked_case("review-decision")
        claimed = self.client.post(
            f"/api/v1/reviews/{case_id}/claim",
            json={"expected_version": 1},
            headers=self.analyst_headers,
        )
        self.assertEqual(claimed.status_code, 200, claimed.text)
        self.assertEqual(claimed.json()["version"], 2)

        stale_claim = self.client.post(
            f"/api/v1/reviews/{case_id}/claim",
            json={"expected_version": 1},
            headers=self.other_headers,
        )
        self.assertEqual(stale_claim.status_code, 409)

        wrong_reviewer = self.client.post(
            f"/api/v1/reviews/{case_id}/decision",
            json={
                "expected_version": 2,
                "decision": "false_positive",
                "reason": "The evidence belongs to the assigned reviewer.",
            },
            headers=self.other_headers,
        )
        self.assertEqual(wrong_reviewer.status_code, 409)

        decided = self.client.post(
            f"/api/v1/reviews/{case_id}/decision",
            json={
                "expected_version": 2,
                "decision": "false_positive",
                "reason": "Verified customer behavior and trusted device history.",
            },
            headers=self.analyst_headers,
        )
        self.assertEqual(decided.status_code, 200, decided.text)
        self.assertEqual(decided.json()["status"], "resolved")
        self.assertEqual(decided.json()["version"], 3)

        connection = sqlite3.connect(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE review_actions SET reason = 'changed' WHERE case_id = ?",
                    (case_id,),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM review_actions WHERE case_id = ?",
                    (case_id,),
                )
            connection.rollback()
            original = connection.execute(
                "SELECT is_blocked, ensemble_risk_score FROM transactions_ledger "
                "WHERE transaction_id = 'review-decision'"
            ).fetchone()
            self.assertEqual(original, (1, 0.95))
        finally:
            connection.close()

    def test_admin_assignment_escalation_and_reopen(self) -> None:
        case_id = self.create_blocked_case("review-escalation", risk_score=0.8)

        forbidden = self.client.post(
            f"/api/v1/reviews/{case_id}/assign",
            json={
                "expected_version": 1,
                "assigned_to_user_id": self.analyst.id,
                "reason": "Assigning the case to an available reviewer.",
            },
            headers=self.analyst_headers,
        )
        self.assertEqual(forbidden.status_code, 403)

        assigned = self.client.post(
            f"/api/v1/reviews/{case_id}/assign",
            json={
                "expected_version": 1,
                "assigned_to_user_id": self.analyst.id,
                "reason": "Assigning the case to an available reviewer.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)
        self.assertEqual(assigned.json()["priority"], "high")

        escalated = self.client.post(
            f"/api/v1/reviews/{case_id}/decision",
            json={
                "expected_version": 2,
                "decision": "needs_more_information",
                "reason": "Merchant evidence is incomplete and requires escalation.",
            },
            headers=self.analyst_headers,
        )
        self.assertEqual(escalated.status_code, 200, escalated.text)
        self.assertEqual(escalated.json()["status"], "escalated")

        analyst_reopen = self.client.post(
            f"/api/v1/reviews/{case_id}/reopen",
            json={
                "expected_version": 3,
                "reason": "Trying to reopen without administrator permission.",
            },
            headers=self.analyst_headers,
        )
        self.assertEqual(analyst_reopen.status_code, 403)

        reopened = self.client.post(
            f"/api/v1/reviews/{case_id}/reopen",
            json={
                "expected_version": 3,
                "reason": "Additional merchant evidence is now available for review.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(reopened.json()["status"], "open")
        self.assertIsNone(reopened.json()["current_decision"])
        self.assertEqual(reopened.json()["version"], 4)

    def test_admin_override_appends_instead_of_replacing(self) -> None:
        case_id = self.create_blocked_case("review-override")
        self.client.post(
            f"/api/v1/reviews/{case_id}/claim",
            json={"expected_version": 1},
            headers=self.analyst_headers,
        )
        self.client.post(
            f"/api/v1/reviews/{case_id}/decision",
            json={
                "expected_version": 2,
                "decision": "confirmed_fraud",
                "reason": "Velocity and device evidence confirm coordinated fraud.",
            },
            headers=self.analyst_headers,
        )

        overridden = self.client.post(
            f"/api/v1/reviews/{case_id}/override",
            json={
                "expected_version": 3,
                "decision": "false_positive",
                "reason": "Administrator verified a controlled internal test transaction.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(overridden.status_code, 200, overridden.text)
        self.assertEqual(overridden.json()["current_decision"], "false_positive")

        detail = self.client.get(
            f"/api/v1/reviews/{case_id}",
            headers=self.admin_headers,
        ).json()
        decisions = [
            action["decision"]
            for action in detail["actions"]
            if action["decision"] is not None
        ]
        self.assertEqual(decisions, ["confirmed_fraud", "false_positive"])
        self.assertEqual(detail["actions"][-1]["action_type"], "overridden")

    def test_queue_filters_pagination_and_reason_validation(self) -> None:
        self.create_blocked_case("review-filter")
        queue = self.client.get(
            "/api/v1/reviews?status=open&priority=critical&limit=1&offset=0",
            headers=self.analyst_headers,
        )
        self.assertEqual(queue.status_code, 200, queue.text)
        self.assertEqual(queue.json()["limit"], 1)
        self.assertLessEqual(len(queue.json()["items"]), 1)
        self.assertGreaterEqual(queue.json()["total"], 1)

        invalid_reason = self.client.post(
            f"/api/v1/reviews/{queue.json()['items'][0]['id']}/decision",
            json={
                "expected_version": 1,
                "decision": "confirmed_fraud",
                "reason": "          ",
            },
            headers=self.analyst_headers,
        )
        self.assertEqual(invalid_reason.status_code, 422)


if __name__ == "__main__":
    unittest.main()
