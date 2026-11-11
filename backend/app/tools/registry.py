"""
Controlled, allowlisted Tool Registry for conversational citizen assistance.
Strictly separates read-only evaluation tools from proposal staging tools.
Zero model database writes: model cannot confirm or execute database modifications.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.chat import ChatConversation, PendingAction
from app.schemas.beneficiary import BeneficiaryCreate, BeneficiaryUpdate
from app.schemas.profile import UserProfileUpdate
from app.services import scheme_service, beneficiary_service, eligibility_service, document_service, application_service, tracking_service
from app.tools.schemas import (
    SearchSchemesInput,
    GetSchemeDetailsInput,
    ListBeneficiariesInput,
    GetBeneficiaryInput,
    EvaluateEligibilityInput,
    EvaluateAllSchemesInput,
    GetDocumentChecklistInput,
    GenerateApplicationDraftInput,
    TrackApplicationStatusInput,
    ProposeCreateBeneficiaryInput,
    ProposeUpdateBeneficiaryInput,
    ProposeUpdateUserProfileInput,
    ToolResult,
    PendingActionProposalResult,
)

logger = logging.getLogger(__name__)

READ_ONLY_TOOLS = {
    "search_schemes",
    "get_scheme_details",
    "list_beneficiaries",
    "get_beneficiary",
    "evaluate_eligibility",
    "evaluate_all_schemes",
    "get_document_checklist",
    "track_application_status",
}

APPLICATION_TOOLS = {
    "generate_application_draft",
}

PROPOSAL_TOOLS = {
    "propose_create_beneficiary",
    "propose_update_beneficiary",
    "propose_update_user_profile",
}

ALLOWLISTED_TOOLS = READ_ONLY_TOOLS | APPLICATION_TOOLS | PROPOSAL_TOOLS

PROHIBITED_CONFIRMATION_TOOLS = {
    "confirm_beneficiary_creation",
    "confirm_profile_update",
    "confirm_action",
    "execute_write",
    "execute_sql",
    "submit_application",
    "submit_external_application",
}


def search_schemes_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Search active verified welfare schemes by query or category."""
    try:
        params = SearchSchemesInput(**args)
        schemes, total = scheme_service.get_schemes(
            db,
            q=params.q,
            category=params.category,
            page=params.page,
            limit=params.limit,
            include_pending=False,
        )
        data = [
            {
                "id": str(s.id),
                "scheme_code": s.scheme_code,
                "name": s.name,
                "short_title": s.short_title,
                "ministry": s.ministry,
                "category": s.category,
                "geographic_scope": s.geographic_scope,
            }
            for s in schemes
        ]
        return ToolResult(success=True, data={"items": data, "total": total, "page": params.page, "limit": params.limit})
    except Exception as e:
        logger.warning(f"Error executing search_schemes: {e}")
        return ToolResult(success=False, error=str(e))


def get_scheme_details_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Retrieve detailed scheme information and required documents."""
    try:
        params = GetSchemeDetailsInput(**args)
        scheme = scheme_service.get_scheme_by_id(db, scheme_id=params.scheme_id, include_pending=False)
        if not scheme or scheme.scheme_status != "active":
            return ToolResult(success=False, error=f"Active scheme with ID '{params.scheme_id}' not found.")

        docs = scheme_service.get_active_documents_for_scheme(db, scheme_id=params.scheme_id)
        doc_data = [
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "title": d.title,
                "is_mandatory": d.is_mandatory,
                "guidance": d.guidance,
            }
            for d in docs
        ]

        data = {
            "id": str(scheme.id),
            "scheme_code": scheme.scheme_code,
            "name": scheme.name,
            "short_title": scheme.short_title,
            "description": scheme.description,
            "ministry": scheme.ministry,
            "category": scheme.category,
            "geographic_scope": scheme.geographic_scope,
            "target_beneficiaries": scheme.target_beneficiaries,
            "benefits": scheme.benefits,
            "official_url": scheme.official_url,
            "application_url": scheme.application_url,
            "required_documents": doc_data,
        }
        return ToolResult(success=True, data=data)
    except Exception as e:
        logger.warning(f"Error executing get_scheme_details: {e}")
        return ToolResult(success=False, error=str(e))


def list_beneficiaries_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """List the account holder and all registered family members."""
    try:
        beneficiaries = beneficiary_service.list_beneficiaries(db, user=current_user)
        data = [b.model_dump(mode="json") for b in beneficiaries]
        return ToolResult(success=True, data=data)
    except Exception as e:
        logger.warning(f"Error executing list_beneficiaries: {e}")
        return ToolResult(success=False, error=str(e))


def get_beneficiary_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Retrieve demographics for a specific beneficiary (self or family member)."""
    try:
        params = GetBeneficiaryInput(**args)
        b = beneficiary_service.get_beneficiary(db, user=current_user, beneficiary_id=params.beneficiary_id)
        return ToolResult(success=True, data=b.model_dump(mode="json"))
    except Exception as e:
        logger.warning(f"Error executing get_beneficiary: {e}")
        return ToolResult(success=False, error=str(e))


def evaluate_eligibility_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Execute deterministic statutory rule evaluation for a scheme."""
    try:
        params = EvaluateEligibilityInput(**args)
        result = eligibility_service.evaluate_scheme_for_user(
            db,
            user=current_user,
            scheme_id=params.scheme_id,
            beneficiary_id=params.beneficiary_id,
            profile_override=params.profile_override,
            include_pending=False,
        )
        return ToolResult(success=True, data=result.model_dump(mode="json"))
    except Exception as e:
        logger.warning(f"Error executing evaluate_eligibility: {e}")
        return ToolResult(success=False, error=str(e))


def evaluate_all_schemes_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Batch evaluate all active schemes for a beneficiary."""
    try:
        params = EvaluateAllSchemesInput(**args)
        result = eligibility_service.evaluate_all_schemes_for_user(
            db,
            user=current_user,
            beneficiary_id=params.beneficiary_id,
            category=params.category,
            profile_override=params.profile_override,
            include_pending=False,
        )
        return ToolResult(success=True, data=result.model_dump(mode="json"))
    except Exception as e:
        logger.warning(f"Error executing evaluate_all_schemes: {e}")
        return ToolResult(success=False, error=str(e))


def get_document_checklist_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Retrieve document checklist for a scheme and applicant (self or beneficiary)."""
    try:
        params = GetDocumentChecklistInput(**args)
        checklist = document_service.get_checklist(
            db=db,
            current_user=current_user,
            scheme_id=params.scheme_id,
            beneficiary_id=params.beneficiary_id,
        )
        return ToolResult(success=True, data=checklist.model_dump(mode="json"))
    except Exception as e:
        logger.warning(f"Error executing get_document_checklist: {e}")
        return ToolResult(success=False, error=str(e))


def generate_application_draft_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Prepare and persist an application draft package with prefilled demographics and attached documents."""
    try:
        params = GenerateApplicationDraftInput(**args)
        draft = application_service.create_application_draft(
            db=db,
            current_user=current_user,
            scheme_id=params.scheme_id,
            beneficiary_id=params.beneficiary_id,
            notes=params.notes,
        )
        return ToolResult(success=True, data=draft.model_dump(mode="json"))
    except Exception as e:
        logger.warning(f"Error executing generate_application_draft: {e}")
        return ToolResult(success=False, error=str(e))


def track_application_status_tool(db: Session, current_user: User, args: Dict[str, Any]) -> ToolResult:
    """Track the status, timeline, and latest updates for a citizen's application."""
    try:
        params = TrackApplicationStatusInput(**args)
        summary = tracking_service.get_application_status_summary(
            db=db,
            current_user=current_user,
            application_id=params.application_id,
            external_reference_number=params.external_reference_number,
            scheme_id=params.scheme_id,
        )
        return ToolResult(success=True, data=summary)
    except Exception as e:
        logger.warning(f"Error executing track_application_status: {e}")
        return ToolResult(success=False, error=str(e))


# ── Proposal Tools (Stage durable actions into PostgreSQL pending_actions) ───

def propose_create_beneficiary_tool(
    db: Session, current_user: User, conversation_id: uuid.UUID, args: Dict[str, Any]
) -> ToolResult:
    """
    Stage creation of a family beneficiary.
    Validates input and writes a durable PENDING action to PostgreSQL.
    Does NOT insert into beneficiary_profiles.
    """
    try:
        # Validate against BeneficiaryCreate schema
        validated_data = BeneficiaryCreate(**args)
        payload = validated_data.model_dump(mode="json", exclude_none=True)

        rel = validated_data.relationship
        name = validated_data.full_name
        age_str = f", age ~{validated_data.profile_data.get('approximate_age')}" if validated_data.profile_data and validated_data.profile_data.get('approximate_age') else ""

        summary_en = f"Add family member: {name} ({rel.capitalize()}{age_str})"
        summary_hi = f"परिवार के सदस्य को जोड़ें: {name} ({rel}{age_str})"

        action_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=15)

        pending_action = PendingAction(
            id=action_id,
            conversation_id=conversation_id,
            user_id=current_user.id,
            beneficiary_id=None,
            action_type="create_beneficiary",
            payload=payload,
            summary={"en": summary_en, "hi": summary_hi},
            status="PENDING",
            expires_at=expires_at,
            created_at=now_utc,
        )
        db.add(pending_action)
        db.commit()

        result = PendingActionProposalResult(
            status="pending_confirmation",
            action_id=action_id,
            action_type="create_beneficiary",
            summary_en=summary_en,
            summary_hi=summary_hi,
            expires_at=expires_at,
            proposed_payload=payload,
        )
        return ToolResult(success=True, data=result.model_dump(mode="json"))
    except Exception as e:
        db.rollback()
        logger.warning(f"Error proposing beneficiary creation: {e}")
        return ToolResult(success=False, error=str(e))


def propose_update_beneficiary_tool(
    db: Session, current_user: User, conversation_id: uuid.UUID, args: Dict[str, Any]
) -> ToolResult:
    """
    Stage an update to an existing family beneficiary.
    Validates target beneficiary ownership and writes PENDING action to PostgreSQL.
    Does NOT update beneficiary_profiles.
    """
    try:
        params = ProposeUpdateBeneficiaryInput(**args)
        # Verify beneficiary exists, belongs to current_user, and is NOT 'self'
        target = beneficiary_service.get_beneficiary(db, user=current_user, beneficiary_id=params.beneficiary_id)
        if target.relationship == "self":
            return ToolResult(
                success=False,
                error="Cannot update account-holder (self) via beneficiary update. Use propose_update_user_profile instead.",
            )

        update_fields = params.model_dump(exclude={"beneficiary_id"}, exclude_none=True, mode="json")
        # Validate against BeneficiaryUpdate schema
        validated_update = BeneficiaryUpdate(**update_fields)
        payload = validated_update.model_dump(mode="json", exclude_none=True)

        summary_en = f"Update details for family member: {target.full_name} ({target.relationship})"
        summary_hi = f"परिवार के सदस्य का विवरण अपडेट करें: {target.full_name} ({target.relationship})"

        action_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=15)

        pending_action = PendingAction(
            id=action_id,
            conversation_id=conversation_id,
            user_id=current_user.id,
            beneficiary_id=params.beneficiary_id,
            action_type="update_beneficiary",
            payload=payload,
            summary={"en": summary_en, "hi": summary_hi},
            status="PENDING",
            expires_at=expires_at,
            created_at=now_utc,
        )
        db.add(pending_action)
        db.commit()

        result = PendingActionProposalResult(
            status="pending_confirmation",
            action_id=action_id,
            action_type="update_beneficiary",
            summary_en=summary_en,
            summary_hi=summary_hi,
            expires_at=expires_at,
            proposed_payload=payload,
        )
        return ToolResult(success=True, data=result.model_dump(mode="json"))
    except Exception as e:
        db.rollback()
        logger.warning(f"Error proposing beneficiary update: {e}")
        return ToolResult(success=False, error=str(e))


def propose_update_user_profile_tool(
    db: Session, current_user: User, conversation_id: uuid.UUID, args: Dict[str, Any]
) -> ToolResult:
    """
    Stage an update to the authenticated account holder's personal profile (UserProfile).
    Writes PENDING action to PostgreSQL.
    Does NOT update user_profiles.
    """
    try:
        params = ProposeUpdateUserProfileInput(**args)
        validated_data = UserProfileUpdate(**params.model_dump(exclude_none=True))
        payload = validated_data.model_dump(mode="json", exclude_none=True)

        summary_en = "Update your account profile details"
        summary_hi = "अपने व्यक्तिगत प्रोफ़ाइल का विवरण अपडेट करें"

        action_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=15)

        pending_action = PendingAction(
            id=action_id,
            conversation_id=conversation_id,
            user_id=current_user.id,
            beneficiary_id=None,
            action_type="update_user_profile",
            payload=payload,
            summary={"en": summary_en, "hi": summary_hi},
            status="PENDING",
            expires_at=expires_at,
            created_at=now_utc,
        )
        db.add(pending_action)
        db.commit()

        result = PendingActionProposalResult(
            status="pending_confirmation",
            action_id=action_id,
            action_type="update_user_profile",
            summary_en=summary_en,
            summary_hi=summary_hi,
            expires_at=expires_at,
            proposed_payload=payload,
        )
        return ToolResult(success=True, data=result.model_dump(mode="json"))
    except Exception as e:
        db.rollback()
        logger.warning(f"Error proposing user profile update: {e}")
        return ToolResult(success=False, error=str(e))


# ── Tool Dispatch Router ─────────────────────────────────────────────────────

def execute_tool(
    db: Session,
    current_user: User,
    conversation_id: uuid.UUID,
    tool_name: str,
    arguments: Dict[str, Any],
) -> ToolResult:
    """
    Execute a strictly allowlisted tool with user authorization and independent validation.
    Hard security check: rejects model attempts to invoke confirmation or direct write tools.
    """
    if tool_name in PROHIBITED_CONFIRMATION_TOOLS:
        logger.error(f"Security block: model attempted to invoke prohibited tool '{tool_name}'")
        return ToolResult(
            success=False,
            error=(
                f"Security violation: Action '{tool_name}' cannot be executed by AI. "
                "The citizen must explicitly confirm this action through the confirmation endpoint."
            ),
        )

    if tool_name not in ALLOWLISTED_TOOLS:
        logger.warning(f"Rejected unknown tool execution attempt: '{tool_name}'")
        return ToolResult(
            success=False,
            error=f"Unknown or unauthorized tool: '{tool_name}'. Available tools: {sorted(list(ALLOWLISTED_TOOLS))}",
        )

    if tool_name == "search_schemes":
        return search_schemes_tool(db, current_user, arguments)
    elif tool_name == "get_scheme_details":
        return get_scheme_details_tool(db, current_user, arguments)
    elif tool_name == "list_beneficiaries":
        return list_beneficiaries_tool(db, current_user, arguments)
    elif tool_name == "get_beneficiary":
        return get_beneficiary_tool(db, current_user, arguments)
    elif tool_name == "evaluate_eligibility":
        return evaluate_eligibility_tool(db, current_user, arguments)
    elif tool_name == "evaluate_all_schemes":
        return evaluate_all_schemes_tool(db, current_user, arguments)
    elif tool_name == "get_document_checklist":
        return get_document_checklist_tool(db, current_user, arguments)
    elif tool_name == "generate_application_draft":
        return generate_application_draft_tool(db, current_user, arguments)
    elif tool_name == "track_application_status":
        return track_application_status_tool(db, current_user, arguments)
    elif tool_name == "propose_create_beneficiary":
        return propose_create_beneficiary_tool(db, current_user, conversation_id, arguments)
    elif tool_name == "propose_update_beneficiary":
        return propose_update_beneficiary_tool(db, current_user, conversation_id, arguments)
    elif tool_name == "propose_update_user_profile":
        return propose_update_user_profile_tool(db, current_user, conversation_id, arguments)

    return ToolResult(success=False, error=f"Unhandled tool: '{tool_name}'")


# ── Gemini Function Declarations Specification ───────────────────────────────

def get_gemini_tools_declarations() -> List[Dict[str, Any]]:
    """
    Return Google Gemini REST API compatible function declarations.
    Tools declared here are strictly limited to read-only queries and staging proposals.
    """
    return [
        {
            "name": "search_schemes",
            "description": "Search active, verified government welfare schemes by keyword or category.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "q": {
                        "type": "STRING",
                        "description": "Search query or keyword (e.g. 'pension', 'kisan', 'health')",
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Category filter (e.g. 'agriculture', 'health', 'senior_citizens')",
                    },
                    "page": {"type": "INTEGER", "description": "Page number (defaults to 1)"},
                    "limit": {"type": "INTEGER", "description": "Maximum schemes to return (defaults to 10, max 20)"},
                },
            },
        },
        {
            "name": "get_scheme_details",
            "description": "Retrieve comprehensive details, benefits, application links, and required documents for a scheme.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "scheme_id": {
                        "type": "STRING",
                        "description": "UUID of the scheme to retrieve",
                    }
                },
                "required": ["scheme_id"],
            },
        },
        {
            "name": "list_beneficiaries",
            "description": "List the authenticated citizen (self) and all registered family members (father, mother, spouse, etc.).",
            "parameters": {
                "type": "OBJECT",
                "properties": {},
            },
        },
        {
            "name": "get_beneficiary",
            "description": "Retrieve demographics for a specific beneficiary under the account holder.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "beneficiary_id": {
                        "type": "STRING",
                        "description": "UUID of the beneficiary (or user profile ID for self)",
                    }
                },
                "required": ["beneficiary_id"],
            },
        },
        {
            "name": "evaluate_eligibility",
            "description": "Deterministically evaluate statutory welfare eligibility for a scheme against a beneficiary.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "scheme_id": {
                        "type": "STRING",
                        "description": "UUID of the scheme to evaluate",
                    },
                    "beneficiary_id": {
                        "type": "STRING",
                        "description": "Optional UUID of target beneficiary (null evaluates the account holder self)",
                    },
                    "profile_override": {
                        "type": "OBJECT",
                        "description": "Optional temporary profile overrides for exploratory what-if evaluation",
                    },
                },
                "required": ["scheme_id"],
            },
        },
        {
            "name": "evaluate_all_schemes",
            "description": "Batch evaluate all active welfare schemes for a beneficiary.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "beneficiary_id": {
                        "type": "STRING",
                        "description": "Optional UUID of beneficiary (null evaluates account holder self)",
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional welfare category filter",
                    },
                },
            },
        },
        {
            "name": "get_document_checklist",
            "description": (
                "Retrieve the document readiness checklist for a specific scheme and applicant (account holder or family beneficiary). "
                "Shows uploaded versus missing documents, accepted alternatives, and official guidance on where to obtain missing papers."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "scheme_id": {
                        "type": "STRING",
                        "description": "UUID of the scheme to get document requirements for",
                    },
                    "beneficiary_id": {
                        "type": "STRING",
                        "description": "Optional UUID of family beneficiary (null checks account holder self)",
                    },
                },
                "required": ["scheme_id"],
            },
        },
        {
            "name": "generate_application_draft",
            "description": (
                "Prepare an application draft package for citizen review: prefill demographic snapshot, "
                "link matching uploaded documents, evaluate rule snapshot, and provide the official portal handoff URL. "
                "Does NOT submit directly to external government portals."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "scheme_id": {
                        "type": "STRING",
                        "description": "UUID of the scheme to prepare draft for",
                    },
                    "beneficiary_id": {
                        "type": "STRING",
                        "description": "Optional UUID of family beneficiary (null prepares for self)",
                    },
                    "notes": {
                        "type": "STRING",
                        "description": "Optional citizen application preparation notes",
                    },
                },
                "required": ["scheme_id"],
            },
        },
        {
            "name": "track_application_status",
            "description": (
                "Track the status, progress, reference number, and latest timeline updates of a citizen's welfare scheme application. "
                "Citizen can query by scheme, application ID, or external government reference number in Hindi or English."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "application_id": {
                        "type": "STRING",
                        "description": "Optional UUID of the application draft to track",
                    },
                    "external_reference_number": {
                        "type": "STRING",
                        "description": "Optional official government portal application reference number (e.g. 'PMKISAN-2026-9812')",
                    },
                    "scheme_id": {
                        "type": "STRING",
                        "description": "Optional UUID of the welfare scheme to check latest application status for",
                    },
                },
            },
        },
        {
            "name": "propose_create_beneficiary",
            "description": (
                "Stage adding a new family member under the citizen's account for their explicit review and confirmation. "
                "Does NOT save to database until confirmed by citizen. Never invent exact date_of_birth from age."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "full_name": {"type": "STRING", "description": "Full name of family member"},
                    "relationship": {
                        "type": "STRING",
                        "enum": ["father", "mother", "spouse", "son", "daughter", "sibling", "guardian", "other"],
                        "description": "Family relationship to account holder",
                    },
                    "date_of_birth": {
                        "type": "STRING",
                        "description": "YYYY-MM-DD format ONLY if explicitly stated by citizen. DO NOT INVENT from age.",
                    },
                    "gender": {"type": "STRING", "description": "Gender (male, female, other)"},
                    "state": {"type": "STRING", "description": "State name"},
                    "district": {"type": "STRING", "description": "District name"},
                    "residence_type": {
                        "type": "STRING",
                        "enum": ["rural", "urban", "semi_urban"],
                        "description": "Residence classification (rural, urban, semi_urban)",
                    },
                    "occupation": {"type": "STRING", "description": "Occupation"},
                    "annual_family_income": {"type": "NUMBER", "description": "Annual family income in INR"},
                    "profile_data": {
                        "type": "OBJECT",
                        "description": "Additional attributes (e.g. approximate_age, caste, bpl_card)",
                    },
                },
                "required": ["full_name", "relationship"],
            },
        },
        {
            "name": "propose_update_beneficiary",
            "description": (
                "Stage an update to an existing family member beneficiary for citizen review and confirmation. "
                "Does NOT update database until confirmed by citizen."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "beneficiary_id": {
                        "type": "STRING",
                        "description": "UUID of the family member beneficiary to update",
                    },
                    "full_name": {"type": "STRING", "description": "Updated full name"},
                    "relationship": {
                        "type": "STRING",
                        "enum": ["father", "mother", "spouse", "son", "daughter", "sibling", "guardian", "other"],
                    },
                    "date_of_birth": {"type": "STRING", "description": "YYYY-MM-DD if explicitly provided"},
                    "gender": {"type": "STRING"},
                    "state": {"type": "STRING"},
                    "district": {"type": "STRING"},
                    "residence_type": {"type": "STRING", "enum": ["rural", "urban", "semi_urban"]},
                    "occupation": {"type": "STRING"},
                    "annual_family_income": {"type": "NUMBER"},
                    "profile_data": {"type": "OBJECT"},
                },
                "required": ["beneficiary_id"],
            },
        },
        {
            "name": "propose_update_user_profile",
            "description": (
                "Stage an update to the authenticated citizen's own account profile (UserProfile) for explicit review. "
                "Does NOT update database until confirmed by citizen."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "full_name": {"type": "STRING"},
                    "date_of_birth": {"type": "STRING", "description": "YYYY-MM-DD if explicitly stated"},
                    "gender": {"type": "STRING"},
                    "state": {"type": "STRING"},
                    "district": {"type": "STRING"},
                    "residence_type": {"type": "STRING", "enum": ["rural", "urban", "semi_urban"]},
                    "occupation": {"type": "STRING"},
                    "annual_family_income": {"type": "NUMBER"},
                    "preferred_language": {"type": "STRING", "enum": ["hi", "en"]},
                    "profile_data": {"type": "OBJECT"},
                },
            },
        },
    ]
