"""Transactional state machine for human review cases."""

import json
import sqlite3
from datetime import datetime, timezone

from app.models.review import (
    ReviewAction,
    ReviewActionType,
    ReviewCase,
    ReviewDecision,
    ReviewPriority,
    ReviewStatus,
)
from app.models.user import User
from app.core.config import SystemRiskConfig


class ReviewNotFoundError(LookupError):
    """Raised when a requested review case does not exist."""


class ReviewTransitionError(ValueError):
    """Raised when a requested transition is invalid for the current state."""


class ReviewConflictError(RuntimeError):
    """Raised when another reviewer changed the case first."""


class ReviewerNotFoundError(LookupError):
    """Raised when an assignment target is missing or inactive."""


def _row_to_case(row) -> ReviewCase | None:
    if not row:
        return None
    return ReviewCase(
        id=row["id"],
        transaction_id=row["transaction_id"],
        status=ReviewStatus(row["status"]),
        priority=ReviewPriority(row["priority"]),
        assigned_to_user_id=row["assigned_to_user_id"],
        analyst_recommendation=ReviewDecision(row["analyst_recommendation"]) if row["analyst_recommendation"] else None,
        final_decision=ReviewDecision(row["final_decision"]) if row["final_decision"] else None,
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        resolved_at=row["resolved_at"],
    )


def _row_to_action(row) -> ReviewAction | None:
    if not row:
        return None
    return ReviewAction(
        id=row["id"],
        case_id=row["case_id"],
        actor_user_id=row["actor_user_id"],
        action_type=ReviewActionType(row["action_type"]),
        previous_status=ReviewStatus(row["previous_status"]) if row["previous_status"] else None,
        resulting_status=ReviewStatus(row["resulting_status"]),
        decision=ReviewDecision(row["decision"]) if row["decision"] else None,
        reason=row["reason"],
        case_version=row["case_version"],
        created_at=row["created_at"],
    )


def ensure_review_case_for_blocked_transaction(
    connection: sqlite3.Connection,
    *,
    transaction_id: str,
    risk_score: float,
) -> int:
    """Create one case and initial action, or return the existing case ID."""
    threshold = SystemRiskConfig.CALIBRATED_THRESHOLD
    critical_boundary = threshold + ((1.0 - threshold) * 0.65)
    priority = ReviewPriority.CRITICAL.value if risk_score >= critical_boundary else ReviewPriority.HIGH.value
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO review_cases (
            transaction_id,
            status,
            priority,
            version
        ) VALUES (?, 'open', ?, 1);
        """,
        (transaction_id, priority),
    )
    if cursor.rowcount == 1:
        case_id = int(cursor.lastrowid)
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
                case_version
            ) VALUES (?, NULL, 'created', NULL, 'open', NULL, ?, 1);
            """,
            (
                case_id,
                "Automatically opened for a blocked model decision",
            ),
        )
        return case_id

    existing = connection.execute(
        """
        SELECT id
        FROM review_cases
        WHERE transaction_id = ?;
        """,
        (transaction_id,),
    ).fetchone()
    if existing is None:
        raise RuntimeError("Could not create or load the transaction review case")
    return int(existing["id"])


def get_review_case(connection: sqlite3.Connection, case_id: int) -> ReviewCase:
    row = connection.execute(
        """
        SELECT * FROM review_cases WHERE id = ?;
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        raise ReviewNotFoundError("Review case not found")
    return _row_to_case(row)


def list_review_cases(
    connection: sqlite3.Connection,
    *,
    status: ReviewStatus | None = None,
    priority: ReviewPriority | None = None,
    assigned_to_user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ReviewCase], int]:
    filters = []
    params = []
    if status is not None:
        filters.append("status = ?")
        params.append(status.value)
    if priority is not None:
        filters.append("priority = ?")
        params.append(priority.value)
    if assigned_to_user_id is not None:
        filters.append("assigned_to_user_id = ?")
        params.append(assigned_to_user_id)

    where_clause = ""
    if filters:
        where_clause = " WHERE " + " AND ".join(filters)

    count_query = f"SELECT COUNT(*) AS cnt FROM review_cases{where_clause}"
    count_row = connection.execute(count_query, params).fetchone()
    total = int(count_row["cnt"] if count_row else 0)

    query = f"SELECT * FROM review_cases{where_clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    rows = connection.execute(query, params + [limit, offset]).fetchall()
    return [_row_to_case(r) for r in rows], total


def get_case_actions(connection: sqlite3.Connection, case_id: int) -> list[ReviewAction]:
    rows = connection.execute(
        """
        SELECT * FROM review_actions
        WHERE case_id = ?
        ORDER BY case_version ASC, id ASC;
        """,
        (case_id,),
    ).fetchall()
    return [_row_to_action(r) for r in rows]


def get_transaction_context(connection: sqlite3.Connection, transaction_id: str) -> dict:
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
        WHERE transaction_id = ?
        """,
        (transaction_id,),
    ).fetchone()
    if row is None:
        raise ReviewNotFoundError("Transaction context not found")
    return {
        **dict(row),
        "is_blocked": bool(row["is_blocked"]),
        "hydrated_metrics": json.loads(row["hydrated_metrics"] or "{}"),
        "shap_payload": json.loads(row["shap_payload"] or "{}"),
    }


def _transition(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    expected_version: int,
    actor_user_id: int,
    action_type: ReviewActionType,
    resulting_status: ReviewStatus,
    reason: str,
    decision: ReviewDecision | None = None,
    assigned_to_user_id: int | None = None,
    analyst_recommendation: ReviewDecision | None = None,
    final_decision: ReviewDecision | None = None,
    resolved_at: datetime | None = None,
) -> ReviewCase:
    if review_case.version != expected_version:
        raise ReviewConflictError(
            "Review case changed; refresh it before submitting again"
        )

    previous_status = review_case.status
    new_version = expected_version + 1
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    resolved_at_str = resolved_at.isoformat().replace("+00:00", "Z") if resolved_at else None

    try:
        cursor = connection.execute(
            """
            UPDATE review_cases
            SET status = ?,
                assigned_to_user_id = ?,
                analyst_recommendation = ?,
                final_decision = ?,
                version = ?,
                updated_at = ?,
                resolved_at = ?
            WHERE id = ? AND version = ?;
            """,
            (
                resulting_status.value,
                assigned_to_user_id,
                analyst_recommendation.value if analyst_recommendation else None,
                final_decision.value if final_decision else None,
                new_version,
                now_str,
                resolved_at_str,
                review_case.id,
                expected_version,
            )
        )
        if cursor.rowcount != 1:
            raise ReviewConflictError(
                "Review case changed; refresh it before submitting again"
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                review_case.id,
                actor_user_id,
                action_type.value,
                previous_status.value if previous_status else None,
                resulting_status.value,
                decision.value if decision else None,
                " ".join(reason.split()),
                new_version,
                now_str,
            )
        )
    except sqlite3.IntegrityError as exc:
        raise ReviewConflictError(
            "Review case changed; refresh it before submitting again"
        ) from exc

    return get_review_case(connection, review_case.id)


def claim_case(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    reviewer: User,
    expected_version: int,
) -> ReviewCase:
    if review_case.status is not ReviewStatus.OPEN:
        raise ReviewTransitionError("Only open cases can be claimed")
    if review_case.assigned_to_user_id is not None:
        raise ReviewTransitionError("Review case is already assigned")
    return _transition(
        connection,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=reviewer.id,
        action_type=ReviewActionType.CLAIMED,
        resulting_status=ReviewStatus.IN_REVIEW,
        reason="Case claimed by reviewer",
        assigned_to_user_id=reviewer.id,
    )


def assign_case(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    admin: User,
    assigned_to_user_id: int,
    expected_version: int,
    reason: str,
) -> ReviewCase:
    if review_case.status in {ReviewStatus.AWAITING_APPROVAL, ReviewStatus.RESOLVED}:
        raise ReviewTransitionError(
            "Cases awaiting approval or already resolved cannot be assigned"
        )
    from app.services.auth_service import get_user_by_id
    assignee = get_user_by_id(connection, assigned_to_user_id)
    if assignee is None or not assignee.is_active:
        raise ReviewerNotFoundError("Active reviewer not found")
    return _transition(
        connection,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.ASSIGNED,
        resulting_status=ReviewStatus.IN_REVIEW,
        reason=reason,
        assigned_to_user_id=assignee.id,
    )


def submit_decision(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    reviewer: User,
    expected_version: int,
    decision: ReviewDecision,
    reason: str,
) -> ReviewCase:
    if review_case.status is not ReviewStatus.IN_REVIEW:
        raise ReviewTransitionError("Only cases in review can receive a decision")
    if review_case.assigned_to_user_id != reviewer.id:
        raise ReviewTransitionError("Case must be assigned to the acting reviewer")

    return _transition(
        connection,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=reviewer.id,
        action_type=ReviewActionType.RECOMMENDATION_SUBMITTED,
        resulting_status=ReviewStatus.AWAITING_APPROVAL,
        reason=reason,
        decision=decision,
        assigned_to_user_id=reviewer.id,
        analyst_recommendation=decision,
    )


def reopen_case(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    admin: User,
    expected_version: int,
    reason: str,
) -> ReviewCase:
    if review_case.status is not ReviewStatus.RESOLVED:
        raise ReviewTransitionError("Only resolved cases can be reopened")
    return _transition(
        connection,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.REOPENED,
        resulting_status=ReviewStatus.OPEN,
        reason=reason,
        analyst_recommendation=None,
        final_decision=None,
    )


def finalize_decision(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    admin: User,
    expected_version: int,
    decision: ReviewDecision,
    reason: str,
) -> ReviewCase:
    """Record the administrator's final decision after analyst recommendation."""
    if review_case.status is not ReviewStatus.AWAITING_APPROVAL:
        raise ReviewTransitionError("Only recommendations awaiting approval can be finalized")
    if decision is ReviewDecision.NEEDS_MORE_INFORMATION:
        raise ReviewTransitionError(
            "Return the case for more evidence instead of resolving it"
        )
    return _transition(
        connection,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.FINAL_DECISION_SUBMITTED,
        resulting_status=ReviewStatus.RESOLVED,
        reason=reason,
        decision=decision,
        assigned_to_user_id=review_case.assigned_to_user_id,
        analyst_recommendation=review_case.analyst_recommendation,
        final_decision=decision,
        resolved_at=datetime.now(timezone.utc),
    )


def return_for_evidence(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    admin: User,
    expected_version: int,
    reason: str,
) -> ReviewCase:
    """Return an analyst recommendation while retaining case ownership."""
    if review_case.status is not ReviewStatus.AWAITING_APPROVAL:
        raise ReviewTransitionError("Only recommendations awaiting approval can be returned")
    return _transition(
        connection,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.RETURNED_FOR_EVIDENCE,
        resulting_status=ReviewStatus.IN_REVIEW,
        reason=reason,
        assigned_to_user_id=review_case.assigned_to_user_id,
        analyst_recommendation=None,
    )


def override_decision(
    connection: sqlite3.Connection,
    *,
    review_case: ReviewCase,
    admin: User,
    expected_version: int,
    decision: ReviewDecision,
    reason: str,
) -> ReviewCase:
    if review_case.status is not ReviewStatus.RESOLVED:
        raise ReviewTransitionError("Only resolved decisions can be corrected")
    return _transition(
        connection,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.OVERRIDDEN,
        resulting_status=ReviewStatus.RESOLVED,
        reason=reason,
        decision=decision,
        assigned_to_user_id=review_case.assigned_to_user_id,
        analyst_recommendation=review_case.analyst_recommendation,
        final_decision=decision,
        resolved_at=datetime.now(timezone.utc),
    )


def list_reviewer_summaries(connection: sqlite3.Connection) -> list[dict[str, object]]:
    """Return administrator-facing workload and outcome summaries per analyst."""
    rows = connection.execute("""
        SELECT
            users.id AS user_id,
            users.full_name,
            users.email,
            users.is_active,
            COUNT(DISTINCT review_cases.id) AS assigned_cases,
            SUM(CASE WHEN review_cases.analyst_recommendation IS NOT NULL THEN 1 ELSE 0 END)
                AS recommendations_submitted,
            SUM(CASE WHEN review_cases.final_decision IS NOT NULL THEN 1 ELSE 0 END)
                AS finalized_cases,
            SUM(CASE
                WHEN review_cases.final_decision IS NOT NULL
                 AND review_cases.final_decision = review_cases.analyst_recommendation
                THEN 1 ELSE 0 END) AS agreements,
            AVG(CASE
                WHEN review_cases.resolved_at IS NOT NULL
                THEN (julianday(review_cases.resolved_at) - julianday(review_cases.created_at)) * 86400.0
                ELSE NULL END) AS average_resolution_seconds
        FROM users
        LEFT JOIN review_cases ON review_cases.assigned_to_user_id = users.id
        WHERE users.role = 'analyst'
        GROUP BY users.id, users.full_name, users.email, users.is_active
        ORDER BY users.full_name;
    """).fetchall()
    summaries = []
    for row in rows:
        finalized = int(row["finalized_cases"] or 0)
        summaries.append({
            "user_id": int(row["user_id"]),
            "full_name": str(row["full_name"]),
            "email": str(row["email"]),
            "is_active": bool(row["is_active"]),
            "assigned_cases": int(row["assigned_cases"] or 0),
            "recommendations_submitted": int(row["recommendations_submitted"] or 0),
            "finalized_cases": finalized,
            "agreement_rate": round(int(row["agreements"] or 0) / finalized, 6) if finalized else None,
            "average_resolution_seconds": round(float(row["average_resolution_seconds"]), 3) if row["average_resolution_seconds"] is not None else None,
        })
    return summaries
