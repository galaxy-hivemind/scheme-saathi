"""
Scheme Saathi AI Agent & Voice Assistant API Endpoints.
Multilingual conversational interface supporting Marathi, Hindi, and English.
"""
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_optional_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services import agent_service

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
