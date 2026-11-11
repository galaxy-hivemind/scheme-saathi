"""create_chat_and_pending_action_tables

Revision ID: a1b2c3d4e5f6
Revises: f2c4b5e6d7a8
Create Date: 2026-11-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2c4b5e6d7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chat_conversations, chat_messages, and pending_actions tables."""
    # 1. chat_conversations
    op.create_table(
        "chat_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("beneficiary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("beneficiary_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False, server_default=sa.text("'New Conversation'")),
        sa.Column("language", sa.String(10), nullable=False, server_default=sa.text("'hi'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("context_state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("char_length(trim(language)) > 0", name="ck_chat_conversations_language"),
        sa.CheckConstraint("status IN ('active', 'archived', 'closed')", name="ck_chat_conversations_status"),
    )
    op.create_index("ix_chat_conversations_user_id", "chat_conversations", ["user_id"])
    op.create_index("ix_chat_conversations_beneficiary_id", "chat_conversations", ["beneficiary_id"])
    op.create_index("ix_chat_conversations_user_updated", "chat_conversations", ["user_id", "updated_at"])

    # 2. chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("response_type", sa.String(50), nullable=False, server_default=sa.text("'text'")),
        sa.Column("structured_data", postgresql.JSONB(), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name="ck_chat_messages_role"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index("ix_chat_messages_conv_created", "chat_messages", ["conversation_id", "created_at"])

    # 3. pending_actions
    op.create_table(
        "pending_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("beneficiary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("beneficiary_profiles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action_type IN ('create_beneficiary', 'update_beneficiary', 'update_user_profile')",
            name="ck_pending_actions_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'EXECUTED', 'CANCELLED', 'EXPIRED')",
            name="ck_pending_actions_status",
        ),
    )
    op.create_index("ix_pending_actions_conversation_id", "pending_actions", ["conversation_id"])
    op.create_index("ix_pending_actions_user_id", "pending_actions", ["user_id"])
    op.create_index("ix_pending_actions_beneficiary_id", "pending_actions", ["beneficiary_id"])
    op.create_index("ix_pending_actions_expires_at", "pending_actions", ["expires_at"])
    op.create_index("ix_pending_actions_user_status", "pending_actions", ["user_id", "status"])
    op.create_index("ix_pending_actions_conv_status", "pending_actions", ["conversation_id", "status"])


def downgrade() -> None:
    """Drop pending_actions, chat_messages, and chat_conversations tables."""
    # 1. Drop pending_actions
    op.drop_index("ix_pending_actions_conv_status", table_name="pending_actions")
    op.drop_index("ix_pending_actions_user_status", table_name="pending_actions")
    op.drop_index("ix_pending_actions_expires_at", table_name="pending_actions")
    op.drop_index("ix_pending_actions_beneficiary_id", table_name="pending_actions")
    op.drop_index("ix_pending_actions_user_id", table_name="pending_actions")
    op.drop_index("ix_pending_actions_conversation_id", table_name="pending_actions")
    op.drop_table("pending_actions")

    # 2. Drop chat_messages
    op.drop_index("ix_chat_messages_conv_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    # 3. Drop chat_conversations
    op.drop_index("ix_chat_conversations_user_updated", table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_beneficiary_id", table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_user_id", table_name="chat_conversations")
    op.drop_table("chat_conversations")
