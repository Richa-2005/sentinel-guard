"""Authenticated APIs for human review cases and decisions."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth_dependencies import AdminUser, AnalystUser, CurrentUser, get_db_conn
from app.models.review import ReviewPriority, ReviewStatus
from app.schemas.review import (
    ReviewAssignRequest,
    ReviewCaseDetail,
    ReviewCasePage,
    ReviewCaseResponse,
    ReviewClaimRequest,
    ReviewDecisionRequest,
    ReviewReopenRequest,
    ReviewReturnRequest,
    ReviewerSummary,
)
from app.services.review_service import (
    ReviewConflictError,
    ReviewerNotFoundError,
    ReviewNotFoundError,
    ReviewTransitionError,
    assign_case,
    claim_case,
    finalize_decision,
    get_case_actions,
    get_review_case,
    get_transaction_context,
    list_review_cases,
    list_reviewer_summaries,
    override_decision,
    reopen_case,
    return_for_evidence,
    submit_decision,
)


router = APIRouter(prefix="/api/v1/reviews", tags=["Human Review"])
DatabaseConnection = Annotated[sqlite3.Connection, Depends(get_db_conn)]


def _serialize_case(connection: sqlite3.Connection, review_case) -> ReviewCaseResponse:
    data = ReviewCaseResponse.model_validate(review_case).model_dump()
    if review_case.assigned_to_user_id is not None:
        if getattr(review_case, "reviewer_name", None) is not None:
            data["assigned_reviewer"] = {
                "id": review_case.assigned_to_user_id,
                "full_name": review_case.reviewer_name,
                "email": review_case.reviewer_email,
            }
        else:
            from app.services.auth_service import get_user_by_id
            reviewer = get_user_by_id(connection, review_case.assigned_to_user_id)
            if reviewer is not None:
                data["assigned_reviewer"] = {
                    "id": reviewer.id,
                    "full_name": reviewer.full_name,
                    "email": reviewer.email,
                }
    return ReviewCaseResponse(**data)


def _raise_review_http_error(error: Exception) -> None:
    if isinstance(error, ReviewNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, ReviewerNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, (ReviewTransitionError, ReviewConflictError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    raise error


@router.get("", response_model=ReviewCasePage)
def read_review_queue(
    current_user: CurrentUser,
    connection: DatabaseConnection,
    case_status: ReviewStatus | None = Query(default=None, alias="status"),
    priority: ReviewPriority | None = None,
    assigned_to_me: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return a filterable, paginated queue for authenticated reviewers."""
    cases, total = list_review_cases(
        connection,
        status=case_status,
        priority=priority,
        assigned_to_user_id=current_user.id if assigned_to_me else None,
        limit=limit,
        offset=offset,
    )
    return ReviewCasePage(
        items=[_serialize_case(connection, item) for item in cases],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/reviewers/summary", response_model=list[ReviewerSummary])
def read_reviewer_summaries(
    _admin: AdminUser,
    connection: DatabaseConnection,
):
    """Return per-analyst workload and outcome summaries."""
    return list_reviewer_summaries(connection)


@router.get("/{case_id}", response_model=ReviewCaseDetail)
def read_review_case(
    case_id: int,
    _current_user: CurrentUser,
    connection: DatabaseConnection,
):
    """Return current state, model evidence, and immutable human history."""
    try:
        review_case = get_review_case(connection, case_id)
    except ReviewNotFoundError as exc:
        _raise_review_http_error(exc)

    case_data = _serialize_case(connection, review_case).model_dump()
    return ReviewCaseDetail(
        **case_data,
        transaction=get_transaction_context(connection, review_case.transaction_id),
        actions=get_case_actions(connection, review_case.id),
    )


@router.post("/{case_id}/claim", response_model=ReviewCaseResponse)
def claim_review_case(
    case_id: int,
    payload: ReviewClaimRequest,
    current_user: AnalystUser,
    connection: DatabaseConnection,
):
    """Atomically claim one currently open case."""
    try:
        result = claim_case(
            connection,
            review_case=get_review_case(connection, case_id),
            reviewer=current_user,
            expected_version=payload.expected_version,
        )
        return _serialize_case(connection, result)
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/recommendation", response_model=ReviewCaseResponse)
def decide_review_case(
    case_id: int,
    payload: ReviewDecisionRequest,
    current_user: AnalystUser,
    connection: DatabaseConnection,
):
    """Append a decision by the reviewer currently assigned to the case."""
    try:
        result = submit_decision(
            connection,
            review_case=get_review_case(connection, case_id),
            reviewer=current_user,
            expected_version=payload.expected_version,
            decision=payload.decision,
            reason=payload.reason,
        )
        return _serialize_case(connection, result)
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/assign", response_model=ReviewCaseResponse)
def assign_review_case(
    case_id: int,
    payload: ReviewAssignRequest,
    admin: AdminUser,
    connection: DatabaseConnection,
):
    """Assign or reassign a non-resolved case as an administrator."""
    try:
        result = assign_case(
            connection,
            review_case=get_review_case(connection, case_id),
            admin=admin,
            assigned_to_user_id=payload.assigned_to_user_id,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
        return _serialize_case(connection, result)
    except (
        ReviewNotFoundError,
        ReviewerNotFoundError,
        ReviewTransitionError,
        ReviewConflictError,
    ) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/reopen", response_model=ReviewCaseResponse)
def reopen_review_case(
    case_id: int,
    payload: ReviewReopenRequest,
    admin: AdminUser,
    connection: DatabaseConnection,
):
    """Reopen a resolved case as an administrator."""
    try:
        result = reopen_case(
            connection,
            review_case=get_review_case(connection, case_id),
            admin=admin,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
        return _serialize_case(connection, result)
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/override", response_model=ReviewCaseResponse)
def override_review_decision(
    case_id: int,
    payload: ReviewDecisionRequest,
    admin: AdminUser,
    connection: DatabaseConnection,
):
    """Append an administrator decision without rewriting prior history."""
    try:
        result = override_decision(
            connection,
            review_case=get_review_case(connection, case_id),
            admin=admin,
            expected_version=payload.expected_version,
            decision=payload.decision,
            reason=payload.reason,
        )
        return _serialize_case(connection, result)
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/finalize", response_model=ReviewCaseResponse)
def finalize_review_decision(
    case_id: int,
    payload: ReviewDecisionRequest,
    admin: AdminUser,
    connection: DatabaseConnection,
):
    """Record the administrator's attributable final decision."""
    try:
        result = finalize_decision(
            connection,
            review_case=get_review_case(connection, case_id),
            admin=admin,
            expected_version=payload.expected_version,
            decision=payload.decision,
            reason=payload.reason,
        )
        return _serialize_case(connection, result)
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/return", response_model=ReviewCaseResponse)
def return_review_for_evidence(
    case_id: int,
    payload: ReviewReturnRequest,
    admin: AdminUser,
    connection: DatabaseConnection,
):
    """Return a recommendation to its assigned analyst with instructions."""
    try:
        result = return_for_evidence(
            connection,
            review_case=get_review_case(connection, case_id),
            admin=admin,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
        return _serialize_case(connection, result)
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)
