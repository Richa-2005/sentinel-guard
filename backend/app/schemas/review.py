"""API contracts for the human-in-the-loop review workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.review import (
    ReviewActionType,
    ReviewDecision,
    ReviewPriority,
    ReviewStatus,
)


class VersionedRequest(BaseModel):
    """Require the client version used for optimistic concurrency control."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class ReviewClaimRequest(VersionedRequest):
    """Claim an open review case."""


class ReviewAssignRequest(VersionedRequest):
    """Assign a case to one active reviewer."""

    assigned_to_user_id: int = Field(gt=0)
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("reason", mode="after")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 10:
            raise ValueError("reason must contain at least 10 characters")
        return normalized


class ReviewDecisionRequest(VersionedRequest):
    """Submit a review conclusion with mandatory reasoning."""

    decision: ReviewDecision
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("reason", mode="after")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 10:
            raise ValueError("reason must contain at least 10 characters")
        return normalized


class ReviewReopenRequest(VersionedRequest):
    """Explain why an administrator is reopening a case."""

    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("reason", mode="after")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 10:
            raise ValueError("reason must contain at least 10 characters")
        return normalized


class ReviewCaseResponse(BaseModel):
    """Current mutable state of one review case."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: str
    status: ReviewStatus
    priority: ReviewPriority
    assigned_to_user_id: int | None
    current_decision: ReviewDecision | None
    version: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class ReviewActionResponse(BaseModel):
    """One immutable transition in a case history."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    actor_user_id: int | None
    action_type: ReviewActionType
    previous_status: ReviewStatus | None
    resulting_status: ReviewStatus
    decision: ReviewDecision | None
    reason: str
    case_version: int
    created_at: datetime


class ReviewTransactionContext(BaseModel):
    """Original immutable model decision presented to a reviewer."""

    transaction_id: str
    card_id: str
    device_id: str
    merchant_id: str
    timestamp: str
    amount_paise: int
    ensemble_risk_score: float
    is_blocked: bool
    hydrated_metrics: dict[str, Any]
    shap_payload: dict[str, Any]


class ReviewCaseDetail(ReviewCaseResponse):
    """Case state plus original model evidence and immutable action history."""

    transaction: ReviewTransactionContext
    actions: list[ReviewActionResponse]


class ReviewCasePage(BaseModel):
    """Paginated review queue response."""

    items: list[ReviewCaseResponse]
    total: int
    limit: int
    offset: int
