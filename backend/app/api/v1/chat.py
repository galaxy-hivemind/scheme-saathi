"""
Conversational Intake & Agent API Endpoints.
Provides multi-turn AI chat assistance, read-only scheme/eligibility inquiries,
and independent citizen action confirmation / cancellation endpoints.
"""
from typing import List, Dict, Any
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ActionExecutionResponse,
    ActionCancelResponse,
    ConversationSummaryResponse,
    ConversationDetailResponse,
)
from app.services import chat_service

router = APIRouter()


@router.post(
    "/chat",
    response_model=APIResponse[ChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Citizen conversational intake and scheme assistance",
    description="Multi-turn conversation with Scheme Saathi. Executes allowlisted tools and stages proposed actions.",
)
def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ChatResponse]:
    """Process a message from an authenticated citizen."""
    response = chat_service.process_chat_message(db, current_user, request)
    return APIResponse.ok(response)


@router.post(
    "/actions/{action_id}/confirm",
    response_model=APIResponse[ActionExecutionResponse],
    status_code=status.HTTP_200_OK,
    summary="Explicitly confirm and execute a staged pending action",
    description="Acquires row-level lock (FOR UPDATE), checks ownership & expiry, and executes exact persisted payload.",
)
def confirm_action_endpoint(
    action_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ActionExecutionResponse]:
    """Execute confirmed citizen action."""
    response = chat_service.confirm_pending_action(db, current_user, action_id)
    return APIResponse.ok(response)


@router.post(
    "/actions/{action_id}/cancel",
    response_model=APIResponse[ActionCancelResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel a staged pending action",
)
def cancel_action_endpoint(
    action_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ActionCancelResponse]:
    """Cancel a pending action before execution."""
    response = chat_service.cancel_pending_action(db, current_user, action_id)
    return APIResponse.ok(response)


@router.get(
    "/conversations",
    response_model=APIResponse[List[ConversationSummaryResponse]],
    status_code=status.HTTP_200_OK,
    summary="List citizen conversation history",
)
def list_conversations_endpoint(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[ConversationSummaryResponse]]:
    """List conversations for current user."""
    items, _ = chat_service.list_conversations(db, current_user, page=page, limit=limit)
    return APIResponse.ok(items)


@router.get(
    "/conversations/{conversation_id}",
    response_model=APIResponse[ConversationDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve full conversation details and messages",
)
def get_conversation_endpoint(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ConversationDetailResponse]:
    """Retrieve full conversation details."""
    conv = chat_service.get_conversation_detail(db, current_user, conversation_id)
    return APIResponse.ok(conv)
