"""Read structured compliance records from the audit vault."""

from __future__ import annotations

from fastapi import HTTPException


def fetch_compliance_audits(db, limit: int = 200) -> list[dict]:
    """Return newest-first immutable compliance audit records."""
    try:
        with db.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    audit.id,
                    audit.transaction_id,
                    audit.event_type,
                    audit.compliance_memo,
                    audit.created_at,
                    audit.previous_hash,
                    audit.current_hash,
                    ledger.card_id,
                    ledger.timestamp,
                    jobs.status AS job_status
                FROM audit_vault AS audit
                JOIN transactions_ledger AS ledger
                    ON ledger.transaction_id = audit.transaction_id
                LEFT JOIN audit_jobs AS jobs
                    ON jobs.transaction_id = audit.transaction_id
                ORDER BY audit.id DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "transaction_id": row["transaction_id"],
                "event_type": row["event_type"],
                "card_id": row["card_id"],
                "timestamp": row["created_at"],
                "transaction_timestamp": row["timestamp"],
                "previous_hash": row["previous_hash"],
                "current_hash": row["current_hash"],
                "report_text": row["compliance_memo"],
                "status": (
                    str(row["job_status"]).lower()
                    if row["job_status"]
                    else "complete"
                ),
                "is_error": False,
            }
            for row in rows
        ]

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch audit records: {error}",
        ) from error


def fetch_audit_jobs(db, limit: int = 200) -> list[dict]:
    """Return newest-first audit job lifecycle state for UI recovery."""
    try:
        with db.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    jobs.transaction_id,
                    jobs.status,
                    jobs.attempts,
                    jobs.created_at,
                    jobs.started_at,
                    jobs.completed_at,
                    jobs.next_attempt_at,
                    jobs.last_error,
                    ledger.card_id
                FROM audit_jobs AS jobs
                JOIN transactions_ledger AS ledger
                    ON ledger.transaction_id = jobs.transaction_id
                ORDER BY jobs.created_at DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch audit jobs: {error}",
        ) from error
