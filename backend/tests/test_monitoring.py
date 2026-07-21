"""Integration tests for operational model monitoring."""

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-key-with-at-least-32-characters",
)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.engine import URL  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.database import SentinelDatabase  # noqa: E402
from app.core.db_session import get_db  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.user import Roles  # noqa: E402
from app.routers.monitoring import (  # noqa: E402
    get_model_monitoring_service,
    router as monitoring_router,
)
from app.services.auth_service import create_user  # noqa: E402
from app.services.monitoring_service import ModelMonitoringService  # noqa: E402
from app.services.review_service import (  # noqa: E402
    ensure_review_case_for_blocked_transaction,
)


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ModelMonitoringIntegrationTests(unittest.TestCase):
    """Validate metric calculations, score shift, windows, and admin access."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory(
            prefix="sentinel-monitoring-tests-"
        )
        cls.database_path = Path(cls.temporary_directory.name) / "monitoring.db"
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

        cls.database = SentinelDatabase(cls.database_path)
        cls.monitoring_service = ModelMonitoringService(cls.database)
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
        with cls.SessionLocal() as session:
            cls.analyst = create_user(
                session,
                email="monitor-analyst@example.com",
                full_name="Monitor Analyst",
                plain_password="analyst-password",
                role=Roles.ANALYST,
            )
            cls.admin = create_user(
                session,
                email="monitor-admin@example.com",
                full_name="Monitor Admin",
                plain_password="admin-password",
                role=Roles.ADMIN,
            )

        cls.analyst_headers = cls.authorization(cls.analyst.id)
        cls.admin_headers = cls.authorization(cls.admin.id)
        cls.now = datetime.now(timezone.utc).replace(microsecond=0)
        cls.seed_monitoring_data()

        def override_get_db():
            session = cls.SessionLocal()
            try:
                yield session
            finally:
                session.close()

        monitoring_app = FastAPI()
        monitoring_app.include_router(monitoring_router)
        monitoring_app.dependency_overrides[get_db] = override_get_db
        monitoring_app.dependency_overrides[
            get_model_monitoring_service
        ] = lambda: cls.monitoring_service
        cls.client = TestClient(monitoring_app)

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
    def seed_monitoring_data(cls) -> None:
        current_time = iso_utc(cls.now - timedelta(hours=1))
        previous_time = iso_utc(cls.now - timedelta(hours=25))
        old_time = iso_utc(cls.now - timedelta(hours=72))
        case_ids: list[int] = []

        with cls.database.connection() as connection:
            for index in range(40):
                transaction_id = f"previous-{index}"
                connection.execute(
                    """
                    INSERT INTO transactions_ledger VALUES (?, 'card', 'device', 'merchant', ?, 100, 0.1, 0, '{}', '{}')
                    """,
                    (transaction_id, previous_time),
                )

            for index in range(40):
                transaction_id = f"current-{index}"
                is_blocked = 1 if index < 4 else 0
                risk_score = 0.99 if is_blocked else 0.9
                connection.execute(
                    """
                    INSERT INTO transactions_ledger VALUES (?, 'card', 'device', 'merchant', ?, 100, ?, ?, '{}', '{}')
                    """,
                    (transaction_id, current_time, risk_score, is_blocked),
                )
                if is_blocked:
                    case_ids.append(
                        ensure_review_case_for_blocked_transaction(
                            connection,
                            transaction_id=transaction_id,
                            risk_score=risk_score,
                        )
                    )

            connection.execute(
                """
                INSERT INTO transactions_ledger VALUES ('old-transaction', 'card', 'device', 'merchant', ?, 100, 0.99, 1, '{}', '{}')
                """,
                (old_time,),
            )

            created_at = iso_utc(cls.now - timedelta(minutes=30))
            resolved_at = iso_utc(cls.now)
            outcomes = (
                (case_ids[0], "resolved", "confirmed_fraud", resolved_at),
                (case_ids[1], "resolved", "false_positive", resolved_at),
                (case_ids[2], "escalated", "needs_more_information", None),
            )
            for case_id, status, decision, resolution in outcomes:
                connection.execute(
                    """
                    UPDATE review_cases
                    SET status = ?,
                        assigned_to_user_id = ?,
                        current_decision = ?,
                        version = 2,
                        created_at = ?,
                        updated_at = ?,
                        resolved_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        cls.admin.id,
                        decision,
                        created_at,
                        resolved_at,
                        resolution,
                        case_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO review_actions (
                        case_id,
                        actor_user_id,
                        action_type,
                        previous_status,
                        resulting_status,
                        decision,
                        reason,
                        case_version,
                        created_at
                    ) VALUES (?, ?, 'decision_submitted', 'open', ?, ?, ?, 2, ?)
                    """,
                    (
                        case_id,
                        cls.admin.id,
                        status,
                        decision,
                        "Controlled monitoring test disposition",
                        resolved_at,
                    ),
                )

    def test_metric_calculations_and_score_shift(self) -> None:
        report = self.monitoring_service.build_report(
            window_hours=24,
            now=self.now,
        )
        predictions = report["predictions"]
        self.assertEqual(predictions["total"], 40)
        self.assertEqual(predictions["blocked"], 4)
        self.assertEqual(predictions["allowed"], 36)
        self.assertEqual(predictions["blocked_rate"], 0.1)
        self.assertEqual(sum(bucket["count"] for bucket in predictions["score_buckets"]), 40)

        reviews = report["human_review"]
        self.assertEqual(reviews["cases_created"], 4)
        self.assertEqual(reviews["reviewed"], 3)
        self.assertEqual(reviews["resolved"], 2)
        self.assertEqual(reviews["escalated"], 1)
        self.assertEqual(reviews["open"], 1)
        self.assertEqual(reviews["case_coverage_rate"], 1.0)
        self.assertEqual(reviews["decision_completion_rate"], 0.75)
        self.assertEqual(reviews["confirmed_fraud_rate"], 0.5)
        self.assertEqual(reviews["false_positive_rate"], 0.5)
        self.assertAlmostEqual(reviews["average_resolution_seconds"], 1800, delta=0.1)
        self.assertAlmostEqual(reviews["p95_resolution_seconds"], 1800, delta=0.1)

        drift = report["score_drift"]
        self.assertEqual(drift["current_sample_size"], 40)
        self.assertEqual(drift["previous_sample_size"], 40)
        self.assertIsNotNone(drift["psi"])
        self.assertEqual(drift["level"], "significant_shift")

    def test_empty_window_reports_insufficient_data_without_fake_rates(self) -> None:
        future = self.now + timedelta(days=30)
        report = self.monitoring_service.build_report(window_hours=1, now=future)
        self.assertEqual(report["predictions"]["total"], 0)
        self.assertIsNone(report["predictions"]["blocked_rate"])
        self.assertIsNone(report["predictions"]["average_risk_score"])
        self.assertIsNone(report["human_review"]["case_coverage_rate"])
        self.assertIsNone(report["score_drift"]["psi"])
        self.assertEqual(report["score_drift"]["level"], "insufficient_data")

    def test_monitoring_endpoint_is_admin_only_and_validates_window(self) -> None:
        self.assertEqual(self.client.get("/api/v1/monitoring/model").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/v1/monitoring/model",
                headers=self.analyst_headers,
            ).status_code,
            403,
        )

        response = self.client.get(
            "/api/v1/monitoring/model?window_hours=24",
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["model"]["name"], "xgboost_lightgbm_ensemble")
        self.assertEqual(payload["predictions"]["total"], 40)

        invalid_window = self.client.get(
            "/api/v1/monitoring/model?window_hours=0",
            headers=self.admin_headers,
        )
        self.assertEqual(invalid_window.status_code, 422)


if __name__ == "__main__":
    unittest.main()
