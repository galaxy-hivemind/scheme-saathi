"""create_conversation_sessions

Revision ID: f4a9c3d8210b
Revises: e7b2c419fa01
Create Date: 2026-11-12 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f4a9c3d8210b"
down_revision: Union[str, Sequence[str], None] = "e7b2c419fa01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create persistent conversation_sessions table isolated per user and conversation_id."""
    op.create_table(
        "conversation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.String(128), nullable=False),
        sa.Column("active_scheme_code", sa.String(100), nullable=True),
        sa.Column("workflow_step", sa.String(50), nullable=False, server_default="TALK"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("state_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("turns", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "conversation_id", name="uq_conversation_sessions_user_conv"),
    )
    op.create_index("ix_conversation_sessions_user_id", "conversation_sessions", ["user_id"])
    op.create_index("ix_conversation_sessions_conversation_id", "conversation_sessions", ["conversation_id"])
    op.create_index("ix_conversation_sessions_user_updated", "conversation_sessions", ["user_id", "updated_at"])


def downgrade() -> None:
    """Drop conversation_sessions table."""
    op.drop_index("ix_conversation_sessions_user_updated", table_name="conversation_sessions")
    op.drop_index("ix_conversation_sessions_conversation_id", table_name="conversation_sessions")
    op.drop_index("ix_conversation_sessions_user_id", table_name="conversation_sessions")
    op.drop_table("conversation_sessions")
