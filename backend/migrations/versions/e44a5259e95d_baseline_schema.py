"""baseline_schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21 08:36:40.538625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the pre-authentication Sentinel Guard schema."""
    op.create_table(
        "transactions_ledger",
        sa.Column("transaction_id", sa.Text(), nullable=False),
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("merchant_id", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("ensemble_risk_score", sa.Float(), nullable=False),
        sa.Column("is_blocked", sa.Integer(), nullable=False),
        sa.Column("hydrated_metrics", sa.Text(), nullable=True),
        sa.Column("shap_payload", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "amount_paise >= 0",
            name="ck_transactions_ledger_amount_non_negative",
        ),
        sa.CheckConstraint(
            "ensemble_risk_score >= 0 AND ensemble_risk_score <= 1",
            name="ck_transactions_ledger_risk_score_range",
        ),
        sa.CheckConstraint(
            "is_blocked IN (0, 1)",
            name="ck_transactions_ledger_is_blocked_boolean",
        ),
        sa.PrimaryKeyConstraint("transaction_id"),
    )
    op.create_table(
        "merchant_history",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("merchant_id", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_id", "merchant_id"),
    )
    op.create_table(
        "audit_vault",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("compliance_memo", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"),
            nullable=False,
        ),
        sa.Column("previous_hash", sa.Text(), nullable=False),
        sa.Column("current_hash", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(previous_hash) = 64",
            name="ck_audit_vault_previous_hash_length",
        ),
        sa.CheckConstraint(
            "length(current_hash) = 64",
            name="ck_audit_vault_current_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions_ledger.transaction_id"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("current_hash"),
        sa.UniqueConstraint("transaction_id", "event_type"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "audit_jobs",
        sa.Column("transaction_id", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.Text(),
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"),
            nullable=False,
        ),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.Text(),
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="ck_audit_jobs_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_audit_jobs_attempts_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions_ledger.transaction_id"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("transaction_id"),
    )

    op.create_index(
        "idx_ledger_card_time",
        "transactions_ledger",
        ["card_id", "timestamp"],
    )
    op.create_index(
        "idx_ledger_device_time",
        "transactions_ledger",
        ["device_id", "timestamp"],
    )
    op.create_index(
        "idx_audit_jobs_ready",
        "audit_jobs",
        ["status", "next_attempt_at"],
    )

    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS prevent_audit_vault_update
            BEFORE UPDATE ON audit_vault
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'audit_vault records are immutable and cannot be updated'
                );
            END;
        """
    )

    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS prevent_audit_vault_delete
        BEFORE DELETE ON audit_vault
        BEGIN
            SELECT RAISE(
                ABORT,
                'audit_vault records are immutable and cannot be deleted'
            );
        END;
        """
    )


def downgrade() -> None:
    """Remove the complete pre-authentication Sentinel Guard schema."""
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_vault_delete")
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_vault_update")

    op.drop_index("idx_audit_jobs_ready", table_name="audit_jobs")
    op.drop_index("idx_ledger_device_time", table_name="transactions_ledger")
    op.drop_index("idx_ledger_card_time", table_name="transactions_ledger")

    op.drop_table("audit_jobs")
    op.drop_table("audit_vault")
    op.drop_table("merchant_history")
    op.drop_table("transactions_ledger")
