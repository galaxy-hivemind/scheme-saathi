"""
Pydantic schemas for Conversational Intake APIs and Pending Action confirmation.
Uniformly structured for APIResponse[DataT] envelopes.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
from pydantic import BaseModel, Field, ConfigDict


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096, description="Citizen message text")
    conversation_id: Optional[uuid.UUID] = Field(None, description="Existing conversation UUID (null creates new)")
    beneficiary_id: Optional[uuid.UUID] = Field(None, description="Optional target beneficiary UUID")
    language: str = Field(default="hi", pattern="^(hi|en)$", description="Preferred language code ('hi', 'en')")


class PendingActionSummary(BaseModel):
    action_id: uuid.UUID
    action_type: str
    summary_en: str
    summary_hi: str
    expires_at: datetime
    proposed_payload: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    message_id: uuid.UUID
    role: str = "assistant"
    content: str
    response_type: str = Field(
        default="text",
        description="'text', 'scheme_cards', 'eligibility_result', 'confirmation_request', 'question', 'error'",
    )
    structured_data: Optional[Dict[str, Any]] = None
    pending_action: Optional[PendingActionSummary] = None
    created_at: datetime


class ActionExecutionResponse(BaseModel):
    action_id: uuid.UUID
    action_type: str
    status: str = "EXECUTED"
    affected_entity_id: Optional[uuid.UUID] = None
    executed_at: datetime
    message: str


class ActionCancelResponse(BaseModel):
    action_id: uuid.UUID
    status: str = "CANCELLED"
    message: str = "Pending action cancelled."


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    response_type: str
    structured_data: Optional[Dict[str, Any]] = None
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    language: str
    status: str
    updated_at: datetime


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    language: str
    status: str
    beneficiary_id: Optional[uuid.UUID] = None
    context_state: Dict[str, Any]
    messages: List[MessageResponse]
    created_at: datetime
    updated_at: datetime
