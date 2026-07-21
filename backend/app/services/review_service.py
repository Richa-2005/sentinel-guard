"""Transactional state machine for human review cases."""

import json
import sqlite3
from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.review import (
    ReviewAction,
    ReviewActionType,
    ReviewCase,
    ReviewDecision,
    ReviewPriority,
    ReviewStatus,
)
from app.models.user import User


class ReviewNotFoundError(LookupError):
    """Raised when a requested review case does not exist."""


class ReviewTransitionError(ValueError):
    """Raised when a requested transition is invalid for the current state."""


class ReviewConflictError(RuntimeError):
    """Raised when another reviewer changed the case first."""


class ReviewerNotFoundError(LookupError):
    """Raised when an assignment target is missing or inactive."""


def ensure_review_case_for_blocked_transaction(
    connection: sqlite3.Connection,
    *,
    transaction_id: str,
    risk_score: float,
) -> int:
    """Create one case and initial action, or return the existing case ID."""
    priority = (
        ReviewPriority.CRITICAL.value
        if risk_score >= 0.9
        else ReviewPriority.HIGH.value
    )
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


def get_review_case(session: Session, case_id: int) -> ReviewCase:
    review_case = session.get(ReviewCase, case_id)
    if review_case is None:
        raise ReviewNotFoundError("Review case not found")
    return review_case


def list_review_cases(
    session: Session,
    *,
    status: ReviewStatus | None = None,
    priority: ReviewPriority | None = None,
    assigned_to_user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ReviewCase], int]:
    filters = []
    if status is not None:
        filters.append(ReviewCase.status == status)
    if priority is not None:
        filters.append(ReviewCase.priority == priority)
    if assigned_to_user_id is not None:
        filters.append(ReviewCase.assigned_to_user_id == assigned_to_user_id)

    count_statement = select(func.count()).select_from(ReviewCase).where(*filters)
    total = int(session.scalar(count_statement) or 0)
    statement = (
        select(ReviewCase)
        .where(*filters)
        .order_by(ReviewCase.created_at.desc(), ReviewCase.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement)), total


def get_case_actions(session: Session, case_id: int) -> list[ReviewAction]:
    statement = (
        select(ReviewAction)
        .where(ReviewAction.case_id == case_id)
        .order_by(ReviewAction.case_version, ReviewAction.id)
    )
    return list(session.scalars(statement))


def get_transaction_context(session: Session, transaction_id: str) -> dict:
    row = session.execute(
        text(
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
            WHERE transaction_id = :transaction_id
            """
        ),
        {"transaction_id": transaction_id},
    ).mappings().one()
    return {
        **dict(row),
        "is_blocked": bool(row["is_blocked"]),
        "hydrated_metrics": json.loads(row["hydrated_metrics"] or "{}"),
        "shap_payload": json.loads(row["shap_payload"] or "{}"),
    }


def _transition(
    session: Session,
    *,
    review_case: ReviewCase,
    expected_version: int,
    actor_user_id: int,
    action_type: ReviewActionType,
    resulting_status: ReviewStatus,
    reason: str,
    decision: ReviewDecision | None = None,
    assigned_to_user_id: int | None = None,
    current_decision: ReviewDecision | None = None,
    resolved_at: datetime | None = None,
) -> ReviewCase:
    if review_case.version != expected_version:
        raise ReviewConflictError(
            "Review case changed; refresh it before submitting again"
        )

    previous_status = review_case.status
    new_version = expected_version + 1
    now = datetime.now(timezone.utc)
    result = session.execute(
        update(ReviewCase)
        .where(
            ReviewCase.id == review_case.id,
            ReviewCase.version == expected_version,
        )
        .values(
            status=resulting_status,
            assigned_to_user_id=assigned_to_user_id,
            current_decision=current_decision,
            version=new_version,
            updated_at=now,
            resolved_at=resolved_at,
        )
    )
    if result.rowcount != 1:
        session.rollback()
        raise ReviewConflictError(
            "Review case changed; refresh it before submitting again"
        )

    session.add(
        ReviewAction(
            case_id=review_case.id,
            actor_user_id=actor_user_id,
            action_type=action_type,
            previous_status=previous_status,
            resulting_status=resulting_status,
            decision=decision,
            reason=" ".join(reason.split()),
            case_version=new_version,
            created_at=now,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ReviewConflictError(
            "Review case changed; refresh it before submitting again"
        ) from exc

    return get_review_case(session, review_case.id)


def claim_case(
    session: Session,
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
        session,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=reviewer.id,
        action_type=ReviewActionType.CLAIMED,
        resulting_status=ReviewStatus.IN_REVIEW,
        reason="Case claimed by reviewer",
        assigned_to_user_id=reviewer.id,
    )


def assign_case(
    session: Session,
    *,
    review_case: ReviewCase,
    admin: User,
    assigned_to_user_id: int,
    expected_version: int,
    reason: str,
) -> ReviewCase:
    if review_case.status is ReviewStatus.RESOLVED:
        raise ReviewTransitionError("Resolved cases must be reopened before assignment")
    assignee = session.get(User, assigned_to_user_id)
    if assignee is None or not assignee.is_active:
        raise ReviewerNotFoundError("Active reviewer not found")
    return _transition(
        session,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.ASSIGNED,
        resulting_status=ReviewStatus.IN_REVIEW,
        reason=reason,
        assigned_to_user_id=assignee.id,
    )


def submit_decision(
    session: Session,
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

    is_escalated = decision is ReviewDecision.NEEDS_MORE_INFORMATION
    resulting_status = (
        ReviewStatus.ESCALATED if is_escalated else ReviewStatus.RESOLVED
    )
    return _transition(
        session,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=reviewer.id,
        action_type=ReviewActionType.DECISION_SUBMITTED,
        resulting_status=resulting_status,
        reason=reason,
        decision=decision,
        assigned_to_user_id=reviewer.id,
        current_decision=decision,
        resolved_at=None if is_escalated else datetime.now(timezone.utc),
    )


def reopen_case(
    session: Session,
    *,
    review_case: ReviewCase,
    admin: User,
    expected_version: int,
    reason: str,
) -> ReviewCase:
    if review_case.status not in {ReviewStatus.RESOLVED, ReviewStatus.ESCALATED}:
        raise ReviewTransitionError("Only resolved or escalated cases can be reopened")
    return _transition(
        session,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.REOPENED,
        resulting_status=ReviewStatus.OPEN,
        reason=reason,
    )


def override_decision(
    session: Session,
    *,
    review_case: ReviewCase,
    admin: User,
    expected_version: int,
    decision: ReviewDecision,
    reason: str,
) -> ReviewCase:
    if review_case.status not in {ReviewStatus.RESOLVED, ReviewStatus.ESCALATED}:
        raise ReviewTransitionError("Only completed decisions can be overridden")
    is_escalated = decision is ReviewDecision.NEEDS_MORE_INFORMATION
    resulting_status = (
        ReviewStatus.ESCALATED if is_escalated else ReviewStatus.RESOLVED
    )
    return _transition(
        session,
        review_case=review_case,
        expected_version=expected_version,
        actor_user_id=admin.id,
        action_type=ReviewActionType.OVERRIDDEN,
        resulting_status=resulting_status,
        reason=reason,
        decision=decision,
        assigned_to_user_id=admin.id,
        current_decision=decision,
        resolved_at=None if is_escalated else datetime.now(timezone.utc),
    )
