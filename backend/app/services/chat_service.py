"""
Chat service managing conversation lifecycle, multi-turn intake, and pending actions confirmation.
Enforces strict security boundaries:
- Conversations and messages belong strictly to current_user.
- Pending actions use row-level locking (with_for_update) to prevent duplicate execution or race conditions.
- Executes exact persisted payload; client overrides are rejected.
- Directs account holder updates to profile_service, and family updates to beneficiary_service.
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
import uuid
import logging
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.chat import ChatConversation, ChatMessage, PendingAction
from app.core.exceptions import NotFoundError, ConflictError, GoneError, ValidationError
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    PendingActionSummary,
    ActionExecutionResponse,
    ActionCancelResponse,
    ConversationSummaryResponse,
    ConversationDetailResponse,
    MessageResponse,
)
from app.schemas.beneficiary import BeneficiaryCreate, BeneficiaryUpdate
from app.schemas.profile import UserProfileUpdate
from app.services import beneficiary_service, profile_service
from app.agents.orchestrator import ConversationalOrchestrator

logger = logging.getLogger(__name__)


def get_or_create_conversation(
    db: Session,
    user: User,
    conversation_id: Optional[uuid.UUID] = None,
    language: str = "hi",
) -> ChatConversation:
    """
    Retrieve an existing active conversation owned by user or create a new one.
    """
    if conversation_id:
        stmt = (
            select(ChatConversation)
            .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id)
        )
        conv = db.scalar(stmt)
        if not conv:
            raise NotFoundError(f"Conversation with ID '{conversation_id}' not found.")
        return conv

    conv = ChatConversation(
        id=uuid.uuid4(),
        user_id=user.id,
        title="New Conversation",
        language=language,
        status="active",
        context_state={},
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def process_chat_message(
    db: Session,
    user: User,
    request: ChatRequest,
    orchestrator: Optional[ConversationalOrchestrator] = None,
) -> ChatResponse:
    """
    Process an incoming citizen chat message.
    1. Fetches or creates conversation.
    2. Persists citizen message in chat_messages.
    3. Runs orchestrator (Gemini with tool registry, or deterministic fallback).
    4. Persists assistant response in chat_messages.
    5. Returns unified ChatResponse with optional staged pending_action.
    """
    orch = orchestrator or ConversationalOrchestrator()
    conv = get_or_create_conversation(db, user, request.conversation_id, language=request.language)

    now_utc = datetime.now(timezone.utc)

    # 1. Store citizen message
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role="user",
        content=request.message,
        response_type="text",
        created_at=now_utc,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(conv)

    # 2. Run orchestrator turn
    turn_res = orch.process_turn(
        db=db,
        current_user=user,
        conversation=conv,
        user_message=request.message,
        beneficiary_id=request.beneficiary_id,
        language=request.language,
    )

    # 3. Store assistant message
    asst_now = datetime.now(timezone.utc)
    asst_msg = ChatMessage(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role="assistant",
        content=turn_res["content"],
        response_type=turn_res["response_type"],
        structured_data=turn_res.get("structured_data"),
        tool_calls=turn_res.get("tool_calls"),
        created_at=asst_now,
    )
    db.add(asst_msg)

    # 4. Update conversation metadata
    conv.updated_at = asst_now
    if conv.title == "New Conversation":
        snippet = request.message[:40].strip()
        conv.title = snippet if snippet else "Conversation"

    db.commit()

    # 5. Build pending action summary if staged
    pending_summary = None
    if turn_res.get("pending_action"):
        pa_data = turn_res["pending_action"]
        pending_summary = PendingActionSummary(
            action_id=pa_data["action_id"],
            action_type=pa_data["action_type"],
            summary_en=pa_data["summary_en"],
            summary_hi=pa_data["summary_hi"],
            expires_at=pa_data["expires_at"],
            proposed_payload=pa_data.get("proposed_payload"),
        )

    return ChatResponse(
        conversation_id=conv.id,
        message_id=asst_msg.id,
        role="assistant",
        content=turn_res["content"],
        response_type=turn_res["response_type"],
        structured_data=turn_res.get("structured_data"),
        pending_action=pending_summary,
        created_at=asst_now,
    )


def confirm_pending_action(
    db: Session,
    user: User,
    action_id: uuid.UUID,
) -> ActionExecutionResponse:
    """
    Explicit citizen confirmation endpoint handler.
    Guarantees:
    - Atomically locks pending_actions row with FOR UPDATE.
    - Rejects duplicate confirmation (409 Conflict).
    - Rejects expired action (410 Gone).
    - Rejects cross-user access (404 Not Found).
    - Executes exact persisted payload; rejects arbitrary client input.
    - Routes account updates to profile_service, and family updates to beneficiary_service.
    """
    stmt = (
        select(PendingAction)
        .where(PendingAction.id == action_id)
        .with_for_update()
    )
    action = db.scalar(stmt)

    if not action or action.user_id != user.id:
        raise NotFoundError(f"Pending action with ID '{action_id}' not found.")

    if action.status == "EXECUTED":
        raise ConflictError("This action has already been confirmed and executed.")

    if action.status == "CANCELLED":
        raise ConflictError("This action was previously cancelled.")

    if action.status == "EXPIRED":
        raise GoneError("This action has expired. Please propose the update again.")

    # Check expiry
    now_utc = datetime.now(timezone.utc)
    if now_utc > action.expires_at:
        action.status = "EXPIRED"
        db.commit()
        raise GoneError("This action has expired. Please propose the update again.")

    # Execute underlying service using exact persisted payload
    affected_entity_id: Optional[uuid.UUID] = None
    message: str = ""

    if action.action_type == "create_beneficiary":
        ben_create = BeneficiaryCreate(**action.payload)
        new_ben = beneficiary_service.create_beneficiary(db, user=user, data=ben_create)
        affected_entity_id = new_ben.id
        message = f"Family member '{new_ben.full_name}' ({new_ben.relationship}) added successfully."

    elif action.action_type == "update_beneficiary":
        if not action.beneficiary_id:
            raise ValidationError("Action payload missing target beneficiary ID.")
        ben_update = BeneficiaryUpdate(**action.payload)
        updated_ben = beneficiary_service.update_beneficiary(
            db, user=user, beneficiary_id=action.beneficiary_id, data=ben_update
        )
        affected_entity_id = updated_ben.id
        message = f"Family member '{updated_ben.full_name}' updated successfully."

    elif action.action_type == "update_user_profile":
        prof_update = UserProfileUpdate(**action.payload)
        updated_prof = profile_service.update_user_profile(
            db, user_id=user.id, data=prof_update
        )
        affected_entity_id = updated_prof.id
        message = "Account profile updated successfully."

    else:
        raise ValidationError(f"Unsupported action type '{action.action_type}'.")

    # Mark action EXECUTED
    action.status = "EXECUTED"
    action.confirmed_at = now_utc
    action.executed_at = now_utc
    db.commit()

    return ActionExecutionResponse(
        action_id=action.id,
        action_type=action.action_type,
        status="EXECUTED",
        affected_entity_id=affected_entity_id,
        executed_at=now_utc,
        message=message,
    )


def cancel_pending_action(
    db: Session,
    user: User,
    action_id: uuid.UUID,
) -> ActionCancelResponse:
    """Explicitly cancel a staged pending action."""
    stmt = (
        select(PendingAction)
        .where(PendingAction.id == action_id)
        .with_for_update()
    )
    action = db.scalar(stmt)

    if not action or action.user_id != user.id:
        raise NotFoundError(f"Pending action with ID '{action_id}' not found.")

    if action.status != "PENDING":
        raise ConflictError(f"Cannot cancel action with current status '{action.status}'.")

    action.status = "CANCELLED"
    db.commit()

    return ActionCancelResponse(action_id=action.id, status="CANCELLED")


def list_conversations(
    db: Session,
    user: User,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[ConversationSummaryResponse], int]:
    """List paginated conversations for current user."""
    offset = (page - 1) * limit
    stmt = (
        select(ChatConversation)
        .where(ChatConversation.user_id == user.id)
        .order_by(desc(ChatConversation.updated_at))
        .offset(offset)
        .limit(limit)
    )
    convs = db.scalars(stmt).all()

    total = db.scalar(
        select(ChatConversation)
        .where(ChatConversation.user_id == user.id)
    )

    items = [
        ConversationSummaryResponse(
            id=c.id,
            title=c.title,
            language=c.language,
            status=c.status,
            updated_at=c.updated_at,
        )
        for c in convs
    ]
    return items, len(convs)


def get_conversation_detail(
    db: Session,
    user: User,
    conversation_id: uuid.UUID,
) -> ConversationDetailResponse:
    """Retrieve full conversation details with ordered messages."""
    stmt = (
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id)
    )
    conv = db.scalar(stmt)
    if not conv:
        raise NotFoundError(f"Conversation with ID '{conversation_id}' not found.")

    msg_responses = [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            response_type=m.response_type,
            structured_data=m.structured_data,
            created_at=m.created_at,
        )
        for m in conv.messages
    ]

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        language=conv.language,
        status=conv.status,
        beneficiary_id=conv.beneficiary_id,
        context_state=conv.context_state,
        messages=msg_responses,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )
