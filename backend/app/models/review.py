"""ORM models for human review cases and append-only reviewer actions."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_type]


class ReviewStatus(str, enum.Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
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


class ReviewCase(Base):
    """Mutable current state for one transaction's human review workflow."""

    __tablename__ = "review_cases"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        Index("idx_review_cases_queue", "status", "priority", "created_at"),
        Index("idx_review_cases_assignee", "assigned_to_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="status",
        ),
        default=ReviewStatus.OPEN,
        server_default=ReviewStatus.OPEN.value,
        nullable=False,
    )
    priority: Mapped[ReviewPriority] = mapped_column(
        Enum(
            ReviewPriority,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="priority",
        ),
        default=ReviewPriority.HIGH,
        server_default=ReviewPriority.HIGH.value,
        nullable=False,
    )
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", onupdate="RESTRICT", ondelete="SET NULL"),
        nullable=True,
    )
    current_decision: Mapped[ReviewDecision | None] = mapped_column(
        Enum(
            ReviewDecision,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="current_decision",
        ),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ReviewAction(Base):
    """Immutable record of a system or human review transition."""

    __tablename__ = "review_actions"
    __table_args__ = (
        CheckConstraint("case_version > 0", name="case_version_positive"),
        CheckConstraint("length(trim(reason)) >= 2", name="reason_present"),
        UniqueConstraint("case_id", "case_version"),
        Index("idx_review_actions_case_time", "case_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("review_cases.id", onupdate="RESTRICT", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", onupdate="RESTRICT", ondelete="RESTRICT"),
        nullable=True,
    )
    action_type: Mapped[ReviewActionType] = mapped_column(
        Enum(
            ReviewActionType,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="action_type",
        ),
        nullable=False,
    )
    previous_status: Mapped[ReviewStatus | None] = mapped_column(
        Enum(
            ReviewStatus,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="previous_status",
        ),
        nullable=True,
    )
    resulting_status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="resulting_status",
        ),
        nullable=False,
    )
    decision: Mapped[ReviewDecision | None] = mapped_column(
        Enum(
            ReviewDecision,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="decision",
        ),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
