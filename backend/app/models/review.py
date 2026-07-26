import enum
from dataclasses import dataclass

class ReviewStatus(str, enum.Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    ESCALATED = "escalated"

class ReviewPriority(str, enum.Enum):
    HIGH = "high"
    CRITICAL = "critical"

class ReviewDecision(str, enum.Enum):
    CONFIRMED_FRAUD = "confirmed_fraud"
    FALSE_POSITIVE = "false_positive"
    NEEDS_MORE_INFORMATION = "needs_more_information"

class ReviewActionType(str, enum.Enum):
    CREATED = "created"
    CLAIMED = "claimed"
    ASSIGNED = "assigned"
    DECISION_SUBMITTED = "decision_submitted"
    REOPENED = "reopened"
    OVERRIDDEN = "overridden"
    RECOMMENDATION_SUBMITTED = "recommendation_submitted"
    FINAL_DECISION_SUBMITTED = "final_decision_submitted"
    RETURNED_FOR_EVIDENCE = "returned_for_evidence"

@dataclass
class ReviewCase:
    id: int
    transaction_id: str
    status: ReviewStatus
    priority: ReviewPriority
    assigned_to_user_id: int | None
    analyst_recommendation: ReviewDecision | None
    final_decision: ReviewDecision | None
    version: int
    created_at: str
    updated_at: str
    resolved_at: str | None = None
    reviewer_name: str | None = None
    reviewer_email: str | None = None

@dataclass
class ReviewAction:
    id: int
    case_id: int
    actor_user_id: int | None
    action_type: ReviewActionType
    previous_status: ReviewStatus | None
    resulting_status: ReviewStatus
    decision: ReviewDecision | None
    reason: str
    case_version: int
    created_at: str
