"""Add the human review workflow.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REVIEW_STATUSES = "'open', 'in_review', 'resolved', 'escalated'"
REVIEW_PRIORITIES = "'high', 'critical'"
REVIEW_DECISIONS = (
    "'confirmed_fraud', 'false_positive', 'needs_more_information'"
)
REVIEW_ACTION_TYPES = (
    "'created', 'claimed', 'assigned', 'decision_submitted', "
    "'reopened', 'overridden'"
)


def upgrade() -> None:
    """Create mutable cases and immutable review-action history."""
    op.create_table(
        "review_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=9),
            server_default=sa.text("'open'"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(length=8),
            server_default=sa.text("'high'"),
            nullable=False,
        ),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("current_decision", sa.String(length=22), nullable=True),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({REVIEW_STATUSES})",
            name="ck_review_cases_status",
        ),
        sa.CheckConstraint(
            f"priority IN ({REVIEW_PRIORITIES})",
            name="ck_review_cases_priority",
        ),
        sa.CheckConstraint(
            f"current_decision IS NULL OR current_decision IN ({REVIEW_DECISIONS})",
            name="ck_review_cases_current_decision",
        ),
        sa.CheckConstraint("version > 0", name="ck_review_cases_version_positive"),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions_ledger.transaction_id"],
            name="fk_review_cases_transaction_id_transactions_ledger",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["users.id"],
            name="fk_review_cases_assigned_to_user_id_users",
            onupdate="RESTRICT",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review_cases"),
        sa.UniqueConstraint(
            "transaction_id",
            name="uq_review_cases_transaction_id",
        ),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "idx_review_cases_queue",
        "review_cases",
        ["status", "priority", "created_at"],
    )
    op.create_index(
        "idx_review_cases_assignee",
        "review_cases",
        ["assigned_to_user_id", "status"],
    )

    op.create_table(
        "review_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=18), nullable=False),
        sa.Column("previous_status", sa.String(length=9), nullable=True),
        sa.Column("resulting_status", sa.String(length=9), nullable=False),
        sa.Column("decision", sa.String(length=22), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"action_type IN ({REVIEW_ACTION_TYPES})",
            name="ck_review_actions_action_type",
        ),
        sa.CheckConstraint(
            f"previous_status IS NULL OR previous_status IN ({REVIEW_STATUSES})",
            name="ck_review_actions_previous_status",
        ),
        sa.CheckConstraint(
            f"resulting_status IN ({REVIEW_STATUSES})",
            name="ck_review_actions_resulting_status",
        ),
        sa.CheckConstraint(
            f"decision IS NULL OR decision IN ({REVIEW_DECISIONS})",
            name="ck_review_actions_decision",
        ),
        sa.CheckConstraint(
            "case_version > 0",
            name="ck_review_actions_case_version_positive",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) >= 2",
            name="ck_review_actions_reason_present",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["review_cases.id"],
            name="fk_review_actions_case_id_review_cases",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_review_actions_actor_user_id_users",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review_actions"),
        sa.UniqueConstraint(
            "case_id",
            "case_version",
            name="uq_review_actions_case_id",
        ),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "idx_review_actions_case_time",
        "review_actions",
        ["case_id", "created_at"],
    )

    # Preserve review coverage when adopting the feature on a populated ledger.
    op.execute(
        """
        INSERT INTO review_cases (
            transaction_id,
            status,
            priority,
            version,
            created_at,
            updated_at
        )
        SELECT
            transaction_id,
            'open',
            CASE
                WHEN ensemble_risk_score >= 0.9 THEN 'critical'
                ELSE 'high'
            END,
            1,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM transactions_ledger
        WHERE is_blocked = 1;
        """
    )
    op.execute(
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
        )
        SELECT
            id,
            NULL,
            'created',
            NULL,
            'open',
            NULL,
            'Backfilled from a blocked model decision during migration',
            1,
            CURRENT_TIMESTAMP
        FROM review_cases;
        """
    )

    op.execute(
        """
        CREATE TRIGGER prevent_review_actions_update
        BEFORE UPDATE ON review_actions
        BEGIN
            SELECT RAISE(
                ABORT,
                'review_actions records are immutable and cannot be updated'
            );
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_review_actions_delete
        BEFORE DELETE ON review_actions
        BEGIN
            SELECT RAISE(
                ABORT,
                'review_actions records are immutable and cannot be deleted'
            );
        END;
        """
    )


def downgrade() -> None:
    """Remove the complete human review workflow."""
    op.execute("DROP TRIGGER IF EXISTS prevent_review_actions_delete")
    op.execute("DROP TRIGGER IF EXISTS prevent_review_actions_update")
    op.drop_index("idx_review_actions_case_time", table_name="review_actions")
    op.drop_table("review_actions")
    op.drop_index("idx_review_cases_assignee", table_name="review_cases")
    op.drop_index("idx_review_cases_queue", table_name="review_cases")
    op.drop_table("review_cases")
