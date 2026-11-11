"""
Conversational orchestrator for Scheme Saathi citizen assistance.
Orchestrates multi-turn dialogue, tool execution loop, prompt assembly, and graceful deterministic fallback.
Strictly enforces zero-trust boundaries:
- Gemini can call read-only tools and proposal staging tools.
- Gemini CANNOT execute confirmed writes.
- Demographics must never be fabricated.
"""
from typing import Dict, Any, List, Optional
import uuid
import logging
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.chat import ChatConversation, ChatMessage
from app.agents.gemini_client import (
    GeminiRESTClient,
    GeminiError,
    GeminiAuthError,
    GeminiQuotaError,
    GeminiTimeoutError,
    GeminiServiceError,
)
from app.agents.fallback import DeterministicFallbackOrchestrator
from app.tools.registry import execute_tool, get_gemini_tools_declarations

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
You are Scheme Saathi (स्कीम साथी), an empathetic, reliable AI conversational assistant helping Indian citizens discover, understand, and evaluate government welfare schemes.

NON-NEGOTIABLE CORE RULES:
1. STRICT TRUTH & ZERO DEMOGRAPHIC FABRICATION:
   - NEVER invent an exact date of birth from an approximate age (e.g. if the citizen says "I am 62 years old", do NOT invent a date like "1964-05-10" or "1962-01-01". Instead, record approximate_age: 62 in profile_data and leave date_of_birth null).
   - NEVER invent income from occupation (e.g. if the citizen says "I am a farmer", do NOT fabricate annual income).
   - NEVER guess rural vs urban residence from partial addresses or city names unless explicitly confirmed.
   - If statutory eligibility requires an exact attribute that is missing, accept UNKNOWN status and politely ask the citizen for the missing information.

2. SEPARATION OF POWERS & CONFIRMATION:
   - You NEVER calculate statutory eligibility yourself. Always call the 'evaluate_eligibility' or 'evaluate_all_schemes' tools.
   - You CANNOT write directly to citizen profiles. When a citizen wants to add or update family members or their own profile, call the proposal tools ('propose_create_beneficiary', 'propose_update_beneficiary', 'propose_update_user_profile').
   - Inform the citizen that their requested changes have been staged and ask them to confirm through the confirmation button/prompt.

3. LANGUAGE & COMMUNICATION:
   - Respond in the language used by the citizen (Hindi, English, or Hinglish).
   - Be clear, respectful, encouraging, and avoid bureaucratic jargon.
   - Present scheme benefits, required documents, and eligibility conditions in clear bullet points.
"""


class ConversationalOrchestrator:
    """
    Coordinates multi-turn dialogue with Gemini, tool execution, and offline fallback.
    """

    def __init__(
        self,
        gemini_client: Optional[GeminiRESTClient] = None,
        fallback_orchestrator: Optional[DeterministicFallbackOrchestrator] = None,
    ):
        self.client = gemini_client or GeminiRESTClient()
        self.fallback = fallback_orchestrator or DeterministicFallbackOrchestrator()

    def process_turn(
        self,
        db: Session,
        current_user: User,
        conversation: ChatConversation,
        user_message: str,
        beneficiary_id: Optional[uuid.UUID] = None,
        language: str = "hi",
    ) -> Dict[str, Any]:
        """
        Process a single turn of conversation.
        Attempts Gemini processing with tools; falls back deterministically if Gemini is unavailable.
        """
        # If Gemini is not configured, route immediately to offline fallback
        if not self.client.is_configured():
            logger.info("Gemini not configured; routing turn to DeterministicFallbackOrchestrator.")
            fallback_res = self.fallback.process_message(db, current_user, user_message, language=language)
            return {
                "content": fallback_res["content"],
                "response_type": fallback_res.get("response_type", "text"),
                "structured_data": fallback_res.get("structured_data"),
                "pending_action": None,
                "tool_calls": [],
            }

        try:
            return self._run_gemini_turn(db, current_user, conversation, user_message, beneficiary_id, language)
        except (GeminiAuthError, GeminiQuotaError, GeminiTimeoutError, GeminiServiceError, GeminiError) as e:
            logger.warning(f"Gemini API failure ({type(e).__name__}: {e}); gracefully engaging fallback.")
            fallback_res = self.fallback.process_message(db, current_user, user_message, language=language)
            # Prepend notice about direct assistance mode
            notice = "हम सीधे सेवा प्रणाली से जानकारी दिखा रहे हैं (Direct assistance mode active):\n\n"
            return {
                "content": notice + fallback_res["content"],
                "response_type": fallback_res.get("response_type", "text"),
                "structured_data": fallback_res.get("structured_data"),
                "pending_action": None,
                "tool_calls": [],
            }

    def _run_gemini_turn(
        self,
        db: Session,
        current_user: User,
        conversation: ChatConversation,
        user_message: str,
        beneficiary_id: Optional[uuid.UUID],
        language: str,
    ) -> Dict[str, Any]:
        """Execute dialogue turn with Gemini and process tool calls."""
        # 1. Assemble dialogue history (last 10 messages)
        history_msgs = conversation.messages[-10:] if conversation.messages else []
        contents: List[Dict[str, Any]] = []

        for m in history_msgs:
            if m.role in ("user", "assistant"):
                role_name = "user" if m.role == "user" else "model"
                contents.append({
                    "role": role_name,
                    "parts": [{"text": m.content}],
                })

        # Add current user message
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}],
        })

        tools_decl = get_gemini_tools_declarations()

        executed_tool_calls: List[Dict[str, Any]] = []
        pending_action_data: Optional[Dict[str, Any]] = None
        structured_data_accum: Dict[str, Any] = {}
        response_type = "text"

        max_iterations = 3
        for iteration in range(max_iterations):
            gemini_resp = self.client.generate_content(
                contents=contents,
                tools=tools_decl,
                system_instruction=SYSTEM_INSTRUCTION,
            )

            function_calls = gemini_resp.get("function_calls", [])
            text_resp = gemini_resp.get("text", "")

            # If model produced no tool calls, return final response
            if not function_calls:
                return {
                    "content": text_resp or "माफ़ कीजिए, मैं इस समय आपकी बात समझ नहीं पाया। (Please rephrase)",
                    "response_type": response_type,
                    "structured_data": structured_data_accum if structured_data_accum else None,
                    "pending_action": pending_action_data,
                    "tool_calls": executed_tool_calls,
                }

            # Model requested one or more tool executions
            # Append model turn containing functionCall to history
            model_parts = []
            if text_resp:
                model_parts.append({"text": text_resp})
            for fc in function_calls:
                model_parts.append({
                    "functionCall": {
                        "name": fc["name"],
                        "args": fc.get("args", {}),
                    }
                })
            contents.append({"role": "model", "parts": model_parts})

            # Execute tool calls
            for fc in function_calls:
                t_name = fc["name"]
                t_args = fc.get("args", {})

                # If beneficiary_id wasn't passed in args but was set in context/request, provide it
                if beneficiary_id and "beneficiary_id" in t_args and not t_args["beneficiary_id"]:
                    t_args["beneficiary_id"] = str(beneficiary_id)

                tool_res = execute_tool(db, current_user, conversation.id, t_name, t_args)
                executed_tool_calls.append({
                    "name": t_name,
                    "args": t_args,
                    "success": tool_res.success,
                    "data": tool_res.data,
                    "error": tool_res.error,
                })

                # Check if this tool staged a pending action
                if t_name in ("propose_create_beneficiary", "propose_update_beneficiary", "propose_update_user_profile"):
                    if tool_res.success and tool_res.data:
                        pending_action_data = tool_res.data
                        response_type = "confirmation_request"
                elif t_name == "search_schemes":
                    if tool_res.success and tool_res.data:
                        structured_data_accum["schemes"] = tool_res.data.get("items", [])
                        response_type = "scheme_cards"
                elif t_name in ("evaluate_eligibility", "evaluate_all_schemes"):
                    if tool_res.success and tool_res.data:
                        structured_data_accum["eligibility"] = tool_res.data
                        response_type = "eligibility_result"

                # Send function response back to Gemini
                resp_payload = tool_res.data if tool_res.success else {"error": tool_res.error}
                contents.append({
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": t_name,
                                "response": resp_payload,
                            }
                        }
                    ],
                })

        # Return whatever we gathered
        return {
            "content": text_resp or "अनुरोध पूरा किया गया। (Request completed)",
            "response_type": response_type,
            "structured_data": structured_data_accum if structured_data_accum else None,
            "pending_action": pending_action_data,
            "tool_calls": executed_tool_calls,
        }
