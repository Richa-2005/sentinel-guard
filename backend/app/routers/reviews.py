"""Authenticated APIs for human review cases and decisions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import AdminUser, CurrentUser
from app.core.db_session import get_db
from app.models.review import ReviewPriority, ReviewStatus
from app.schemas.review import (
    ReviewAssignRequest,
    ReviewCaseDetail,
    ReviewCasePage,
    ReviewCaseResponse,
    ReviewClaimRequest,
    ReviewDecisionRequest,
    ReviewReopenRequest,
)
from app.services.review_service import (
    ReviewConflictError,
    ReviewerNotFoundError,
    ReviewNotFoundError,
    ReviewTransitionError,
    assign_case,
    claim_case,
    get_case_actions,
    get_review_case,
    get_transaction_context,
    list_review_cases,
    override_decision,
    reopen_case,
    submit_decision,
)


router = APIRouter(prefix="/api/v1/reviews", tags=["Human Review"])
DatabaseSession = Annotated[Session, Depends(get_db)]


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
    session: DatabaseSession,
    case_status: ReviewStatus | None = Query(default=None, alias="status"),
    priority: ReviewPriority | None = None,
    assigned_to_me: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return a filterable, paginated queue for authenticated reviewers."""
    cases, total = list_review_cases(
        session,
        status=case_status,
        priority=priority,
        assigned_to_user_id=current_user.id if assigned_to_me else None,
        limit=limit,
        offset=offset,
    )
    return ReviewCasePage(items=cases, total=total, limit=limit, offset=offset)


@router.get("/{case_id}", response_model=ReviewCaseDetail)
def read_review_case(
    case_id: int,
    _current_user: CurrentUser,
    session: DatabaseSession,
):
    """Return current state, model evidence, and immutable human history."""
    try:
        review_case = get_review_case(session, case_id)
    except ReviewNotFoundError as exc:
        _raise_review_http_error(exc)

    case_data = ReviewCaseResponse.model_validate(review_case).model_dump()
    return ReviewCaseDetail(
        **case_data,
        transaction=get_transaction_context(session, review_case.transaction_id),
        actions=get_case_actions(session, review_case.id),
    )


@router.post("/{case_id}/claim", response_model=ReviewCaseResponse)
def claim_review_case(
    case_id: int,
    payload: ReviewClaimRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Atomically claim one currently open case."""
    try:
        return claim_case(
            session,
            review_case=get_review_case(session, case_id),
            reviewer=current_user,
            expected_version=payload.expected_version,
        )
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/decision", response_model=ReviewCaseResponse)
def decide_review_case(
    case_id: int,
    payload: ReviewDecisionRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Append a decision by the reviewer currently assigned to the case."""
    try:
        return submit_decision(
            session,
            review_case=get_review_case(session, case_id),
            reviewer=current_user,
            expected_version=payload.expected_version,
            decision=payload.decision,
            reason=payload.reason,
        )
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/assign", response_model=ReviewCaseResponse)
def assign_review_case(
    case_id: int,
    payload: ReviewAssignRequest,
    admin: AdminUser,
    session: DatabaseSession,
):
    """Assign or reassign a non-resolved case as an administrator."""
    try:
        return assign_case(
            session,
            review_case=get_review_case(session, case_id),
            admin=admin,
            assigned_to_user_id=payload.assigned_to_user_id,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
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
    session: DatabaseSession,
):
    """Reopen a resolved or escalated case as an administrator."""
    try:
        return reopen_case(
            session,
            review_case=get_review_case(session, case_id),
            admin=admin,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)


@router.post("/{case_id}/override", response_model=ReviewCaseResponse)
def override_review_decision(
    case_id: int,
    payload: ReviewDecisionRequest,
    admin: AdminUser,
    session: DatabaseSession,
):
    """Append an administrator decision without rewriting prior history."""
    try:
        return override_decision(
            session,
            review_case=get_review_case(session, case_id),
            admin=admin,
            expected_version=payload.expected_version,
            decision=payload.decision,
            reason=payload.reason,
        )
    except (ReviewNotFoundError, ReviewTransitionError, ReviewConflictError) as exc:
        _raise_review_http_error(exc)
