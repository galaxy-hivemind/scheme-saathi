"""
Scheme Saathi AI Agent & Voice Assistant API Endpoints.
Multilingual conversational interface supporting Marathi, Hindi, and English.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_optional_current_user, get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.common import APIResponse
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services import agent_service
from app.services.conversation_memory import (
    get_conversation_history_for_user,
    list_conversations_for_user,
)

router = APIRouter()


@router.post(
    "/chat",
    response_model=APIResponse[AgentChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Process citizen multilingual query and return conversational assistance",
)
def chat_with_agent(
    payload: AgentChatRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[AgentChatResponse]:
    """
    Conversational endpoint for Scheme Saathi assistant:
    - Automatically detects Marathi (mr), Hindi (hi), or English (en).
    - Queries PostgreSQL for verified welfare scheme metadata.
    - If user is authenticated, evaluates real eligibility against their profile.
    - Generates concise voice output for browser TTS.
    - Returns structured scheme cards and document checklists.
    """
    response_data = agent_service.process_chat_message(
        db=db,
        request=payload,
        current_user=current_user,
    )
    return APIResponse.ok(response_data)


@router.get(
    "/conversations",
    status_code=status.HTTP_200_OK,
    summary="List persisted conversations belonging to the authenticated citizen",
)
def list_my_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    items = list_conversations_for_user(db=db, current_user=current_user, profile=profile)
    return APIResponse.ok({"conversations": items})


@router.get(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted conversation history and context for the authenticated citizen",
)
def get_my_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    history = get_conversation_history_for_user(
        db=db,
        conv_id=conversation_id,
        current_user=current_user,
        profile=profile,
    )
    if history is None:
        return APIResponse.ok({
            "conversation_id": conversation_id,
            "active_scheme_code": None,
            "workflow_step": "TALK",
            "turns": [],
            "state": {},
        })
    return APIResponse.ok(history)
