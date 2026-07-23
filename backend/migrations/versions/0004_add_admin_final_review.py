"""Separate analyst recommendations from administrator final decisions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REVIEW_STATUSES = "'open', 'in_review', 'awaiting_approval', 'resolved', 'escalated'"
REVIEW_DECISIONS = "'confirmed_fraud', 'false_positive', 'needs_more_information'"
REVIEW_ACTION_TYPES = (
    "'created', 'claimed', 'assigned', 'decision_submitted', 'reopened', "
    "'overridden', 'recommendation_submitted', 'final_decision_submitted', "
    "'returned_for_evidence'"
)


def upgrade() -> None:
    """Add explicit recommendation/final-decision state without rewriting history."""
    op.execute("DROP TRIGGER IF EXISTS prevent_review_actions_delete")
    op.execute("DROP TRIGGER IF EXISTS prevent_review_actions_update")

    op.add_column(
        "review_cases",
        sa.Column("analyst_recommendation", sa.String(length=22), nullable=True),
    )
    op.add_column(
        "review_cases",
        sa.Column("final_decision", sa.String(length=22), nullable=True),
    )
    op.execute(
        """
        UPDATE review_cases
        SET analyst_recommendation = current_decision,
            final_decision = CASE
                WHEN status = 'resolved' THEN current_decision
                ELSE NULL
            END;
        """
    )

    with op.batch_alter_table("review_cases", recreate="always") as batch:
        batch.drop_constraint("ck_review_cases_status", type_="check")
        batch.drop_constraint("ck_review_cases_current_decision", type_="check")
        batch.drop_column("current_decision")
        batch.alter_column(
            "status",
            existing_type=sa.String(length=9),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
        batch.create_check_constraint(
            "ck_review_cases_status",
            f"status IN ({REVIEW_STATUSES})",
        )
        batch.create_check_constraint(
            "ck_review_cases_analyst_recommendation",
            f"analyst_recommendation IS NULL OR analyst_recommendation IN ({REVIEW_DECISIONS})",
        )
        batch.create_check_constraint(
            "ck_review_cases_final_decision",
            f"final_decision IS NULL OR final_decision IN ({REVIEW_DECISIONS})",
        )

    with op.batch_alter_table("review_actions", recreate="always") as batch:
        batch.drop_constraint("ck_review_actions_action_type", type_="check")
        batch.drop_constraint("ck_review_actions_previous_status", type_="check")
        batch.drop_constraint("ck_review_actions_resulting_status", type_="check")
        batch.alter_column(
            "action_type",
            existing_type=sa.String(length=18),
            type_=sa.String(length=28),
            existing_nullable=False,
        )
        batch.alter_column(
            "previous_status",
            existing_type=sa.String(length=9),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
        batch.alter_column(
            "resulting_status",
            existing_type=sa.String(length=9),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
        batch.create_check_constraint(
            "ck_review_actions_action_type",
            f"action_type IN ({REVIEW_ACTION_TYPES})",
        )
        batch.create_check_constraint(
            "ck_review_actions_previous_status",
            f"previous_status IS NULL OR previous_status IN ({REVIEW_STATUSES})",
        )
        batch.create_check_constraint(
            "ck_review_actions_resulting_status",
            f"resulting_status IN ({REVIEW_STATUSES})",
        )

    op.execute(
        "UPDATE review_cases SET status = 'awaiting_approval' WHERE status = 'escalated'"
    )
    op.execute(
        "UPDATE review_actions SET previous_status = 'awaiting_approval' WHERE previous_status = 'escalated'"
    )
    op.execute(
        "UPDATE review_actions SET resulting_status = 'awaiting_approval' WHERE resulting_status = 'escalated'"
    )

    op.execute(
        """
        CREATE TRIGGER prevent_review_actions_update
        BEFORE UPDATE ON review_actions
        BEGIN
            SELECT RAISE(ABORT, 'review_actions records are immutable and cannot be updated');
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_review_actions_delete
        BEFORE DELETE ON review_actions
        BEGIN
            SELECT RAISE(ABORT, 'review_actions records are immutable and cannot be deleted');
        END;
        """
    )


def downgrade() -> None:
    """Restore the original single-decision representation."""
    op.execute("DROP TRIGGER IF EXISTS prevent_review_actions_delete")
    op.execute("DROP TRIGGER IF EXISTS prevent_review_actions_update")
    op.add_column(
        "review_cases",
        sa.Column("current_decision", sa.String(length=22), nullable=True),
    )
    op.execute(
        "UPDATE review_cases SET current_decision = COALESCE(final_decision, analyst_recommendation)"
    )
    op.execute(
        "UPDATE review_cases SET status = 'escalated' WHERE status = 'awaiting_approval'"
    )
    op.execute(
        "UPDATE review_actions SET previous_status = 'escalated' WHERE previous_status = 'awaiting_approval'"
    )
    op.execute(
        "UPDATE review_actions SET resulting_status = 'escalated' WHERE resulting_status = 'awaiting_approval'"
    )
    with op.batch_alter_table("review_cases", recreate="always") as batch:
        batch.drop_constraint("ck_review_cases_status", type_="check")
        batch.drop_constraint("ck_review_cases_analyst_recommendation", type_="check")
        batch.drop_constraint("ck_review_cases_final_decision", type_="check")
        batch.drop_column("analyst_recommendation")
        batch.drop_column("final_decision")
        batch.alter_column("status", existing_type=sa.String(length=20), type_=sa.String(length=9), existing_nullable=False)
        batch.create_check_constraint("ck_review_cases_status", "status IN ('open', 'in_review', 'resolved', 'escalated')")
        batch.create_check_constraint("ck_review_cases_current_decision", f"current_decision IS NULL OR current_decision IN ({REVIEW_DECISIONS})")
    op.execute(
        """
        CREATE TRIGGER prevent_review_actions_update BEFORE UPDATE ON review_actions
        BEGIN SELECT RAISE(ABORT, 'review_actions records are immutable and cannot be updated'); END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_review_actions_delete BEFORE DELETE ON review_actions
        BEGIN SELECT RAISE(ABORT, 'review_actions records are immutable and cannot be deleted'); END;
        """
    )
