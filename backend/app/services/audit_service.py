"""Atomic, hash-chained audit-vault persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta

from app.core.database import SentinelDatabase


GENESIS_HASH = "0" * 64

def _utc_now() -> str:
    """Return UTC in the same sortable format used by SQLite."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

class AuditVaultService:
    """Append immutable compliance records to the audit hash chain."""

    def __init__(self, database: SentinelDatabase) -> None:
        self.database = database

    def append_audit(
        self,
        transaction_id: str,
        event_type: str,
        compliance_memo: str,
    ) -> dict[str, object]:
        created_at = _utc_now()

        with self.database.connection() as connection:
            # Acquire the SQLite write lock before reading the chain head.
            connection.execute("BEGIN IMMEDIATE;")

            previous_row = connection.execute(
                """
                SELECT current_hash
                FROM audit_vault
                ORDER BY id DESC
                LIMIT 1;
                """
            ).fetchone()

            previous_hash = (
                previous_row["current_hash"]
                if previous_row is not None
                else GENESIS_HASH
            )

            hash_payload = json.dumps(
                {
                    "transaction_id": transaction_id,
                    "event_type": event_type,
                    "compliance_memo": compliance_memo,
                    "created_at": created_at,
                    "previous_hash": previous_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )

            current_hash = hashlib.sha256(
                hash_payload.encode("utf-8")
            ).hexdigest()

            cursor = connection.execute(
                """
                INSERT INTO audit_vault (
                    transaction_id,
                    event_type,
                    compliance_memo,
                    created_at,
                    previous_hash,
                    current_hash
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    transaction_id,
                    event_type,
                    compliance_memo,
                    created_at,
                    previous_hash,
                    current_hash,
                ),
            )

            completed_at = _utc_now()

            job_update = connection.execute(
                """
                UPDATE audit_jobs
                SET status = 'COMPLETED',
                    completed_at = ?,
                    last_error = NULL
                WHERE transaction_id = ?
                AND status = 'PROCESSING';
                """,
                (completed_at, transaction_id),
            )

            if job_update.rowcount != 1:
                raise RuntimeError(
                    f"Could not complete audit job for transaction {transaction_id}"
                )

        return {
            "id": cursor.lastrowid,
            "transaction_id": transaction_id,
            "event_type": event_type,
            "compliance_memo": compliance_memo,
            "created_at": created_at,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
        }
    
    def claim_job(self, transaction_id: str) -> bool:
        now = _utc_now()

        with self.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE;")

            cursor = connection.execute(
                """
                UPDATE audit_jobs
                SET status = 'PROCESSING',
                    attempts = attempts + 1,
                    started_at = ?,
                    last_error = NULL
                WHERE transaction_id = ?
                AND status = 'PENDING'
                AND next_attempt_at <= ?;
                """,
                (now, transaction_id, now),
            )

        return cursor.rowcount == 1
    
    def record_job_failure(
        self,
        transaction_id: str,
        error: Exception,
        max_attempts: int = 3,
    ) -> dict[str, object]:
        """Schedule a retry or permanently fail an exhausted audit job."""
        error_message = str(error)[:2000]

        with self.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE;")

            job = connection.execute(
                """
                SELECT attempts
                FROM audit_jobs
                WHERE transaction_id = ?
                AND status = 'PROCESSING';
                """,
                (transaction_id,),
            ).fetchone()

            if job is None:
                raise RuntimeError(
                    f"No processing audit job found for {transaction_id}"
                )

            attempts = int(job["attempts"])

            if attempts >= max_attempts:
                connection.execute(
                    """
                    UPDATE audit_jobs
                    SET status = 'FAILED',
                        last_error = ?
                    WHERE transaction_id = ?
                    AND status = 'PROCESSING';
                    """,
                    (error_message, transaction_id),
                )

                return {
                    "transaction_id": transaction_id,
                    "status": "FAILED",
                    "attempts": attempts,
                    "next_attempt_at": None,
                }

            delay_seconds = 5 * (2 ** (attempts - 1))
            retry_at = (
                datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z")

            connection.execute(
                """
                UPDATE audit_jobs
                SET status = 'PENDING',
                    started_at = NULL,
                    next_attempt_at = ?,
                    last_error = ?
                WHERE transaction_id = ?
                AND status = 'PROCESSING';
                """,
                (retry_at, error_message, transaction_id),
            )

            return {
                "transaction_id": transaction_id,
                "status": "PENDING",
                "attempts": attempts,
                "next_attempt_at": retry_at,
            }
        
    def load_job_context(
        self,
        transaction_id: str,
    ) -> tuple[dict, dict, dict]:
        """Load the exact decision data originally stored in the ledger."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT
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
                FROM transactions_ledger
                WHERE transaction_id = ?;
                """,
                (transaction_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Transaction {transaction_id} does not exist"
            )

        raw_data = {
            "transaction_id": row["transaction_id"],
            "card_id": row["card_id"],
            "device_id": row["device_id"],
            "merchant_id": row["merchant_id"],
            "timestamp": row["timestamp"],
            "amount_paise": row["amount_paise"],
            "ensemble_risk_score": row["ensemble_risk_score"],
            "is_blocked": bool(row["is_blocked"]),
        }

        hydrated_metrics = json.loads(
            row["hydrated_metrics"] or "{}"
        )
        shap_payload = json.loads(
            row["shap_payload"] or "{}"
        )

        return raw_data, hydrated_metrics, shap_payload
    
    def find_ready_jobs(self, limit: int = 5) -> list[str]:
        """Find pending jobs whose retry time has arrived."""
        now = _utc_now()

        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT transaction_id
                FROM audit_jobs
                WHERE status = 'PENDING'
                AND next_attempt_at <= ?
                ORDER BY next_attempt_at, created_at
                LIMIT ?;
                """,
                (now, limit),
            ).fetchall()

        return [str(row["transaction_id"]) for row in rows]
    
    def recover_interrupted_jobs(self) -> int:
        """Return jobs abandoned by a terminated process to the queue."""
        now = _utc_now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE audit_jobs
                SET status = 'PENDING',
                    started_at = NULL,
                    next_attempt_at = ?,
                    last_error = 'Recovered after interrupted backend process'
                WHERE status = 'PROCESSING';
                """,
                (now,),
            )

        return cursor.rowcount
