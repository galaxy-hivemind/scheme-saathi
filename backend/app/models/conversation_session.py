"""
ConversationSession ORM model for persistent multi-turn assistant memory.
Strictly isolated by user_id and conversation_id.
"""
from typing import TYPE_CHECKING, Optional, Dict, Any, List
import uuid
from sqlalchemy import String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ConversationSession(Base, TimestampMixin):
    __tablename__ = "conversation_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "conversation_id", name="uq_conversation_sessions_user_conv"),
        Index("ix_conversation_sessions_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    active_scheme_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    workflow_step: Mapped[str] = mapped_column(
        String(50),
        default="TALK",
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )
    state_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
    )
    turns: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=list,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
