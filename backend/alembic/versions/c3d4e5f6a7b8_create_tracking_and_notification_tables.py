"""create_tracking_and_notification_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-11 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create application_status_history and notifications tables, and expand application_drafts status check constraint."""
    # 1. Expand application_drafts status check constraint
    op.drop_constraint("ck_application_drafts_status", "application_drafts", type_="check")
    op.create_check_constraint(
        "ck_application_drafts_status",
        "application_drafts",
        "status IN ('DRAFT', 'READY', 'SUBMITTED', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'DISBURSED', 'ARCHIVED')",
    )

    # 2. application_status_history
    op.create_table(
        "application_status_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "source_type",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'user_reported'"),
        ),
        sa.Column("source_reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'READY', 'SUBMITTED', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'DISBURSED', 'ARCHIVED')",
            name="ck_status_history_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('user_reported', 'official_integration', 'portal_sync', 'admin_action')",
            name="ck_status_history_source",
        ),
    )
    op.create_index(
        "ix_app_status_history_app_id",
        "application_status_history",
        ["application_id"],
    )
    op.create_index(
        "ix_app_status_history_app_created",
        "application_status_history",
        ["application_id", "created_at"],
    )

    # 3. notifications
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "notification_type",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'status_update'"),
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'NORMAL'"),
        ),
        sa.Column(
            "channels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"in_app\"]'::jsonb"),
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(
            "notification_type IN ('status_update', 'document_expiry', 'action_required', 'system')",
            name="ck_notifications_type",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'NORMAL', 'HIGH', 'URGENT')",
            name="ck_notifications_priority",
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_app_id", "notifications", ["application_id"])
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Drop notifications and application_status_history tables, and revert application_drafts status check constraint."""
    # 1. Drop notifications
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_app_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    # 2. Drop application_status_history
    op.drop_index(
        "ix_app_status_history_app_created",
        table_name="application_status_history",
    )
    op.drop_index(
        "ix_app_status_history_app_id",
        table_name="application_status_history",
    )
    op.drop_table("application_status_history")

    # 3. Revert application_drafts status check constraint
    op.drop_constraint("ck_application_drafts_status", "application_drafts", type_="check")
    op.create_check_constraint(
        "ck_application_drafts_status",
        "application_drafts",
        "status IN ('DRAFT', 'READY', 'SUBMITTED', 'ARCHIVED')",
    )
