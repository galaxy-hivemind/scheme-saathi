"""
Chat conversation, message, and pending action models for conversational citizen assistance.
Stores multi-turn conversational context, active intents, tool execution logs, and durable staged actions.
"""
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.beneficiary_profile import BeneficiaryProfile


class ChatConversation(Base, TimestampMixin):
    __tablename__ = "chat_conversations"

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
        doc="Owning authenticated account holder ID",
    )
    beneficiary_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beneficiary_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Currently targeted family beneficiary (null means self)",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Conversation",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="hi",
        doc="Preferred language code ('hi', 'en')",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        doc="Conversation lifecycle status ('active', 'archived', 'closed')",
    )
    context_state: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
        doc="Structured dialogue state (intent, extracted attributes, active scheme, state version)",
    )

    # Relationships
    user: Mapped["User"] = orm_relationship(
        "User",
        back_populates="conversations",
    )
    beneficiary: Mapped[Optional["BeneficiaryProfile"]] = orm_relationship(
        "BeneficiaryProfile",
    )
    messages: Mapped[List["ChatMessage"]] = orm_relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )
    pending_actions: Mapped[List["PendingAction"]] = orm_relationship(
        "PendingAction",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="PendingAction.created_at.desc()",
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(trim(language)) > 0",
            name="ck_chat_conversations_language",
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'closed')",
            name="ck_chat_conversations_status",
        ),
        Index("ix_chat_conversations_user_updated", "user_id", "updated_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="'user', 'assistant', 'system', 'tool'",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    response_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="text",
        doc="'text', 'scheme_cards', 'eligibility_result', 'confirmation_request', 'question', 'error'",
    )
    structured_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
        default=None,
    )
    tool_calls: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    conversation: Mapped["ChatConversation"] = orm_relationship(
        "ChatConversation",
        back_populates="messages",
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_chat_messages_role",
        ),
        Index("ix_chat_messages_conv_created", "conversation_id", "created_at"),
    )


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Owning account holder ID",
    )
    beneficiary_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beneficiary_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Target beneficiary affected (null if user profile or new beneficiary)",
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="'create_beneficiary', 'update_beneficiary', 'update_user_profile'",
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        doc="Strictly validated execution payload",
    )
    summary: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        doc="Bilingual summary diff for citizen review",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        doc="'PENDING', 'CONFIRMED', 'EXECUTED', 'CANCELLED', 'EXPIRED'",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Timestamp after which action cannot be confirmed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    conversation: Mapped["ChatConversation"] = orm_relationship(
        "ChatConversation",
        back_populates="pending_actions",
    )
    user: Mapped["User"] = orm_relationship(
        "User",
        back_populates="pending_actions",
    )
    beneficiary: Mapped[Optional["BeneficiaryProfile"]] = orm_relationship(
        "BeneficiaryProfile",
    )

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('create_beneficiary', 'update_beneficiary', 'update_user_profile')",
            name="ck_pending_actions_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'EXECUTED', 'CANCELLED', 'EXPIRED')",
            name="ck_pending_actions_status",
        ),
        Index("ix_pending_actions_user_status", "user_id", "status"),
        Index("ix_pending_actions_conv_status", "conversation_id", "status"),
    )
