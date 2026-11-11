"""
Pydantic schemas for Scheme Saathi AI Assistant & Voice Companion.
Supports multilingual queries in Marathi (mr), Hindi (hi), and English (en).
Evolves into an agentic workflow: TALK → MATCH → CHECKLIST → PRE-FILL → CONFIRM.
"""
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field


class SupportedLanguage(str, Enum):
    MARATHI = "mr"
    HINDI = "hi"
    ENGLISH = "en"
    AUTO = "auto"


class ChatResponseType(str, Enum):
    TEXT = "text"
    SCHEME_CARDS = "scheme_cards"
    ELIGIBILITY_RESULT = "eligibility_result"
    DOCUMENT_CHECKLIST = "document_checklist"
    APPLICATION_GUIDE = "application_guide"
    BENEFITS_INFO = "benefits_info"
    STATUS_TRACKING = "status_tracking"
    FORM_DRAFT = "form_draft"
    CONFIRMATION_REQUEST = "confirmation_request"
    CONFIRMATION_RESULT = "confirmation_result"


class AgentChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="Active conversation session ID")
    message: str = Field(..., min_length=1, max_length=2000, description="Citizen text or speech transcript")
    language: Optional[str] = Field("auto", description="Preferred language code ('mr', 'hi', 'en', 'auto')")
    scheme_id: Optional[str] = Field(None, description="Optional target scheme context")
    workflow_step: Optional[str] = Field(None, description="Current workflow step: TALK, MATCH, CHECKLIST, PRE-FILL, CONFIRM")
    form_action: Optional[str] = Field(None, description="Agentic action: 'save_draft', 'confirm_submit', 'request_checklist', etc.")
    form_data: Optional[Dict[str, Any]] = Field(None, description="Citizen editable form data payload")


class SchemeCardSummary(BaseModel):
    id: str
    scheme_code: str
    name: str
    category: str
    ministry: str
    benefits: str
    eligibility_status: Optional[str] = None
    official_url: Optional[str] = None


class AgentChatResponse(BaseModel):
    conversation_id: str
    message: str
    spoken_text: str = Field(..., description="Concise conversational text optimized for Text-to-Speech")
    detected_language: str = Field(..., description="Language detected or used: 'mr', 'hi', or 'en'")
    response_type: ChatResponseType = Field(default=ChatResponseType.TEXT)
    data: Optional[Any] = Field(None, description="Structured payload: scheme cards, document checklists, or form schemas")
    suggested_followups: List[str] = Field(default_factory=list, description="Follow-up chips")
    requires_action: bool = False
    action_type: Optional[str] = None
    engine_mode: str = Field(default="deterministic", description="Active AI engine mode: 'deterministic' or 'gemini_grounded'")
    
    # Phase 3 Agentic Workflow Fields
    workflow_step: str = Field(default="TALK", description="Active workflow step: TALK, MATCH, CHECKLIST, PRE-FILL, CONFIRM")
    active_scheme: Optional[Dict[str, Any]] = Field(None, description="Currently selected scheme metadata")
    eligibility_summary: Optional[Dict[str, Any]] = Field(None, description="Result of check_eligibility execution")
    checklist_data: Optional[Dict[str, Any]] = Field(None, description="Result of build_checklist execution")
    form_draft_data: Optional[Dict[str, Any]] = Field(None, description="Result of fill_form execution")
    confirmation_data: Optional[Dict[str, Any]] = Field(None, description="Result of submit_form execution")
