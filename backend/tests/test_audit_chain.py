"""Integration tests for audit-vault chain verification."""

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

from app.core.database import SentinelDatabase, initialize_database  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.user import Roles  # noqa: E402
from app.routers.audits import (  # noqa: E402
    get_audit_vault_service,
    router as audit_router,
)
from app.services.audit_service import AuditVaultService, GENESIS_HASH  # noqa: E402
from app.services.auth_service import create_user  # noqa: E402


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


class AuditChainVerificationTests(unittest.TestCase):
    """Verify valid, protected, immutable, and deliberately corrupted chains."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="sentinel-audit-chain-tests-"
        )
        self.database_path = Path(self.temporary_directory.name) / "audit.db"

        self.database = initialize_database(self.database_path)
        self.audit_service = AuditVaultService(self.database)

        with self.database.connection() as conn:
            user = create_user(
                conn,
                email="auditor@example.com",
                full_name="Audit Analyst",
                plain_password="analyst-password",
                role=Roles.ANALYST,
            )
            token, _ = create_access_token(user.id)
        self.headers = {"Authorization": f"Bearer {token}"}

        verification_app = FastAPI()
        verification_app.include_router(audit_router)
        verification_app.dependency_overrides[
            get_audit_vault_service
        ] = lambda: self.audit_service
        self.client = TestClient(verification_app)

    def tearDown(self) -> None:
        self.client.close()
        self.temporary_directory.cleanup()

    def append_audit(self, transaction_id: str, memo: str) -> dict[str, object]:
        with self.database.connection() as connection:
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
                ) VALUES (?, 'card', 'device', 'merchant', ?, 50000, 0.95, 1, '{}', '{}')
                """,
                (transaction_id, "2026-07-21T00:00:00Z"),
            )
            connection.execute(
                """
                INSERT INTO audit_jobs (transaction_id, status, attempts, started_at)
                VALUES (?, 'PROCESSING', 1, ?)
                """,
                (transaction_id, "2026-07-21T00:00:00Z"),
            )
        return self.audit_service.append_audit(
            transaction_id=transaction_id,
            event_type="BLOCKED_TRANSACTION_AUDIT",
            compliance_memo=memo,
        )

    def test_empty_and_valid_chains(self) -> None:
        empty = self.audit_service.verify_chain()
        self.assertTrue(empty["is_valid"])
        self.assertEqual(empty["records_checked"], 0)
        self.assertEqual(empty["head_hash"], GENESIS_HASH)

        first = self.append_audit("audit-one", "First compliance memorandum")
        second = self.append_audit("audit-two", "Second compliance memorandum")
        self.assertEqual(second["previous_hash"], first["current_hash"])

        result = self.audit_service.verify_chain()
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["records_checked"], 2)
        self.assertEqual(result["issue_count"], 0)
        self.assertEqual(result["head_hash"], second["current_hash"])

    def test_endpoint_requires_authentication_and_returns_report(self) -> None:
        self.append_audit("audit-api", "API verification memorandum")
        self.assertEqual(self.client.get("/api/v1/audits/verify").status_code, 401)

        response = self.client.get(
            "/api/v1/audits/verify",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["records_checked"], 1)
        self.assertEqual(report["issues"], [])

    def test_database_immutability_and_tamper_detection(self) -> None:
        first = self.append_audit("audit-tamper-one", "Original first memorandum")
        self.append_audit("audit-tamper-two", "Original second memorandum")

        connection = sqlite3.connect(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE audit_vault SET compliance_memo = 'changed' WHERE id = ?",
                    (first["id"],),
                )
            connection.rollback()

            connection.execute("DROP TRIGGER prevent_audit_vault_update")
            connection.execute(
                "UPDATE audit_vault SET compliance_memo = 'tampered' WHERE id = ?",
                (first["id"],),
            )
            connection.commit()
        finally:
            connection.close()

        content_tamper = self.audit_service.verify_chain()
        self.assertFalse(content_tamper["is_valid"])
        self.assertEqual(content_tamper["first_invalid_record_id"], first["id"])
        self.assertIn(
            "hash_mismatch",
            {issue["code"] for issue in content_tamper["issues"]},
        )

        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "UPDATE audit_vault SET current_hash = ? WHERE id = ?",
                ("f" * 64, first["id"]),
            )
            connection.commit()
        finally:
            connection.close()

        link_tamper = self.audit_service.verify_chain()
        issue_codes = {issue["code"] for issue in link_tamper["issues"]}
        self.assertFalse(link_tamper["is_valid"])
        self.assertIn("hash_mismatch", issue_codes)
        self.assertIn("broken_link", issue_codes)


if __name__ == "__main__":
    unittest.main()
