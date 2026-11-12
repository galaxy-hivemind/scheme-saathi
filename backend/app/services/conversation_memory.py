"""
Persistent Multi-Turn Conversation Memory Service for Scheme Saathi.

Persists and restores structured conversational context across turns and
server/browser restarts while enforcing strict per-citizen AND per-conversation
isolation:
- Active scheme metadata & workflow stage
- Last scheme discovery / eligibility evaluation list (for ordinal & anaphora references)
- Last document checklist & Vault status breakdown (for ordinal doc follow-ups)
- Identified missing documents & citizen document confirmations
- Active application draft ID, lifecycle status & verified reference number
- Bounded conversation turn history for Gemini context & reload hydration
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
import uuid

from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.conversation_session import ConversationSession
from app.models.user import User
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

MAX_STORED_TURNS = 40
MAX_CONVERSATIONS_IN_PROFILE = 30

STATE_KEYS = (
    "active_scheme_code",
    "active_scheme_name",
    "workflow_step",
    "language",
    "last_intent",
    "last_eligibility_results",
    "last_scheme_list",
    "last_checklist",
    "missing_documents",
    "last_discussed_document",
    "citizen_confirmed_documents",
    "active_application_id",
    "application_draft_summary",
    "application_reference",
    "application_status",
    "conversation_entities",
)


def _json_safe(value: Any) -> Any:
    """Recursively coerces values into clean JSON-serializable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _extract_state_snapshot(session: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts structured persistent memory fields from an in-memory session dict."""
    snapshot: Dict[str, Any] = {}
    for key in STATE_KEYS:
        if key in session and session[key] is not None:
            snapshot[key] = _json_safe(session[key])
    snapshot["updated_at"] = datetime.now(timezone.utc).isoformat()
    return snapshot


def _apply_snapshot_to_session(session: Dict[str, Any], snapshot: Dict[str, Any], turns: Optional[List[Dict[str, Any]]] = None) -> None:
    """Hydrates an in-memory session dict from a persisted state snapshot without overwriting fresher explicit keys."""
    if not isinstance(snapshot, dict):
        return
    for key in STATE_KEYS:
        if key in snapshot and snapshot[key] is not None:
            if not session.get(key):
                session[key] = snapshot[key]
    if turns is not None and not session.get("turns"):
        session["turns"] = list(turns)[-MAX_STORED_TURNS:]


def _can_use_db_table(db: Optional[Session]) -> bool:
    """Checks safely whether `db` is a real SQLAlchemy Session bound to an engine."""
    if db is None:
        return False
    return hasattr(db, "execute") and hasattr(db, "commit") and getattr(db, "bind", None) is not None


def _get_user_uuid(current_user: Optional[User], profile: Optional[UserProfile]) -> Optional[uuid.UUID]:
    raw_id = None
    if current_user is not None and getattr(current_user, "id", None) is not None:
        raw_id = current_user.id
    elif profile is not None and getattr(profile, "user_id", None) is not None:
        raw_id = profile.user_id
    if raw_id is None:
        return None
    if isinstance(raw_id, uuid.UUID):
        return raw_id
    try:
        return uuid.UUID(str(raw_id))
    except (ValueError, TypeError):
        return None


def _sync_application_summary_from_profile(
    session: Dict[str, Any],
    profile: Optional[UserProfile],
) -> None:
    """Keeps active application draft summary and verified reference synced with citizen's real DB profile."""
    if not profile or not isinstance(getattr(profile, "profile_data", None), dict):
        return
    apps = profile.profile_data.get("applications")
    if not isinstance(apps, list) or not apps:
        return

    target_scheme = (session.get("active_scheme_code") or "").upper()
    target_app_id = session.get("active_application_id")

    matched_app = None
    if target_app_id:
        matched_app = next((a for a in apps if a.get("id") == target_app_id), None)
    if matched_app is None and target_scheme:
        matched_app = next(
            (
                a for a in apps
                if (a.get("scheme_code") or "").upper() == target_scheme
                and not a.get("legacy_synthetic_submission")
                and not str(a.get("reference_number") or "").upper().startswith("SAATHI/")
            ),
            None,
        )

    if matched_app:
        session["active_application_id"] = matched_app.get("id")
        session["application_status"] = matched_app.get("lifecycle_state") or "draft"
        ref = matched_app.get("reference_number")
        if ref and not str(ref).upper().startswith("SAATHI/"):
            session["application_reference"] = ref
        else:
            session["application_reference"] = None
        session["application_draft_summary"] = {
            "application_id": matched_app.get("id"),
            "scheme_code": matched_app.get("scheme_code"),
            "scheme_name": matched_app.get("scheme_name"),
            "lifecycle_state": matched_app.get("lifecycle_state") or "draft",
            "readiness_percentage": matched_app.get("readiness_percentage"),
            "reference_number": session["application_reference"],
            "form_supported": matched_app.get("schema_available", True),
            "version": matched_app.get("version", 1),
        }


def load_conversation_state(
    db: Optional[Session],
    conv_id: str,
    current_user: Optional[User],
    profile: Optional[UserProfile],
    session: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Loads persisted conversation state into `session` strictly scoped by
    authenticated `user_id` + `conv_id`. Anonymous callers never load user rows.
    """
    user_uuid = _get_user_uuid(current_user, profile)
    if not user_uuid or not conv_id:
        return session

    # 1. Primary relational store: `conversation_sessions`
    loaded_from_db = False
    if _can_use_db_table(db):
        try:
            with db.begin_nested():
                record = db.scalar(
                    select(ConversationSession).where(
                        ConversationSession.user_id == user_uuid,
                        ConversationSession.conversation_id == conv_id,
                    )
                )
            if record is not None:
                snapshot = dict(record.state_data or {})
                if record.active_scheme_code:
                    snapshot.setdefault("active_scheme_code", record.active_scheme_code)
                if record.workflow_step:
                    snapshot.setdefault("workflow_step", record.workflow_step)
                if record.language:
                    snapshot.setdefault("language", record.language)
                _apply_snapshot_to_session(session, snapshot, turns=list(record.turns or []))
                loaded_from_db = True
        except Exception as exc:
            logger.debug("ConversationSession load skipped cleanly: %s", exc)

    # 2. Fallback / unit-test mirror: `profile.profile_data['conversations_by_conv']`
    if not loaded_from_db and profile and isinstance(getattr(profile, "profile_data", None), dict):
        conv_map = profile.profile_data.get("conversations_by_conv")
        if isinstance(conv_map, dict) and conv_id in conv_map and isinstance(conv_map[conv_id], dict):
            entry = conv_map[conv_id]
            _apply_snapshot_to_session(session, entry.get("state") or entry, turns=entry.get("turns"))

        active_map = profile.profile_data.get("active_schemes_by_conv")
        if isinstance(active_map, dict) and conv_id in active_map and isinstance(active_map[conv_id], dict):
            a_entry = active_map[conv_id]
            if a_entry.get("scheme_code") and not session.get("active_scheme_code"):
                session["active_scheme_code"] = a_entry["scheme_code"]
            if a_entry.get("workflow_step") and not session.get("workflow_step"):
                session["workflow_step"] = a_entry["workflow_step"]

    _sync_application_summary_from_profile(session, profile)
    return session


def persist_conversation_state(
    db: Optional[Session],
    conv_id: str,
    current_user: Optional[User],
    profile: Optional[UserProfile],
    session: Dict[str, Any],
) -> None:
    """
    Persists full structured conversation context & turns to PostgreSQL
    (`conversation_sessions` + `user_profiles.profile_data`) isolated by `(user_id, conv_id)`.
    """
    if not conv_id:
        return
    user_uuid = _get_user_uuid(current_user, profile)
    if not user_uuid:
        # Anonymous users stay strictly in-memory; never written to any user record
        return

    _sync_application_summary_from_profile(session, profile)
    snapshot = _extract_state_snapshot(session)
    turns = _json_safe(list(session.get("turns") or [])[-MAX_STORED_TURNS:])

    # 1. Sync compact per-conversation snapshot onto profile_data for restart compatibility
    if profile and hasattr(profile, "profile_data"):
        if not isinstance(profile.profile_data, dict):
            profile.profile_data = {}
        profile.profile_data.pop("active_conversation_scheme", None)

        if session.get("active_scheme_code"):
            active_map = profile.profile_data.get("active_schemes_by_conv")
            if not isinstance(active_map, dict):
                active_map = {}
                profile.profile_data["active_schemes_by_conv"] = active_map
            active_map[conv_id] = {
                "scheme_code": session["active_scheme_code"],
                "workflow_step": session.get("workflow_step") or "TALK",
                "updated_at": snapshot["updated_at"],
            }

        conv_map = profile.profile_data.get("conversations_by_conv")
        if not isinstance(conv_map, dict):
            conv_map = {}
            profile.profile_data["conversations_by_conv"] = conv_map

        conv_map[conv_id] = {
            "state": snapshot,
            "turns": turns[-20:],
            "updated_at": snapshot["updated_at"],
        }
        if len(conv_map) > MAX_CONVERSATIONS_IN_PROFILE:
            sorted_keys = sorted(
                conv_map.keys(),
                key=lambda k: conv_map[k].get("updated_at", "") if isinstance(conv_map[k], dict) else "",
            )
            for old_k in sorted_keys[: len(conv_map) - MAX_CONVERSATIONS_IN_PROFILE]:
                conv_map.pop(old_k, None)

        flag_modified(profile, "profile_data")

    # 2. Persist into dedicated relational table if DB bound
    if _can_use_db_table(db):
        try:
            with db.begin_nested():
                record = db.scalar(
                    select(ConversationSession).where(
                        ConversationSession.user_id == user_uuid,
                        ConversationSession.conversation_id == conv_id,
                    )
                )
                if record is None:
                    record = ConversationSession(
                        user_id=user_uuid,
                        conversation_id=conv_id,
                        active_scheme_code=session.get("active_scheme_code"),
                        workflow_step=session.get("workflow_step") or "TALK",
                        language=session.get("language") or "en",
                        state_data=snapshot,
                        turns=turns,
                    )
                    db.add(record)
                else:
                    record.active_scheme_code = session.get("active_scheme_code")
                    record.workflow_step = session.get("workflow_step") or "TALK"
                    record.language = session.get("language") or record.language or "en"
                    record.state_data = snapshot
                    record.turns = turns
                    flag_modified(record, "state_data")
                    flag_modified(record, "turns")
        except Exception as exc:
            logger.debug("ConversationSession relational persistence skipped: %s", exc)

    if db is not None and hasattr(db, "commit"):
        try:
            db.commit()
        except Exception as exc:
            logger.debug("Conversation state commit skipped cleanly: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass


def record_conversation_turn(
    db: Optional[Session],
    conv_id: str,
    current_user: Optional[User],
    profile: Optional[UserProfile],
    session: Dict[str, Any],
    *,
    user_message: str,
    assistant_response: Any,
    lang: str,
    intent: Optional[str] = None,
    tool_calls: Optional[List[str]] = None,
) -> None:
    """Appends user + assistant turns into session memory and persists to DB."""
    turns: List[Dict[str, Any]] = list(session.get("turns") or [])
    now_iso = datetime.now(timezone.utc).isoformat()

    active_scheme_code = (
        (getattr(assistant_response, "active_scheme", None) or {}).get("scheme_code")
        or session.get("active_scheme_code")
    )
    if active_scheme_code:
        session["active_scheme_code"] = active_scheme_code
    if getattr(assistant_response, "active_scheme", None):
        scheme_name = assistant_response.active_scheme.get("name") or assistant_response.active_scheme.get("scheme_name")
        if scheme_name:
            session["active_scheme_name"] = scheme_name
    if getattr(assistant_response, "workflow_step", None):
        session["workflow_step"] = assistant_response.workflow_step
    session["language"] = lang
    if intent:
        session["last_intent"] = intent

    turns.append({
        "id": f"user-{uuid.uuid4().hex[:8]}",
        "role": "user",
        "content": user_message,
        "language": lang,
        "created_at": now_iso,
    })

    resp_type = getattr(getattr(assistant_response, "response_type", None), "value", None) or str(
        getattr(assistant_response, "response_type", "text")
    )
    turns.append({
        "id": f"asst-{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "content": getattr(assistant_response, "message", ""),
        "spoken_text": getattr(assistant_response, "spoken_text", ""),
        "language": getattr(assistant_response, "detected_language", lang),
        "response_type": resp_type,
        "workflow_step": getattr(assistant_response, "workflow_step", session.get("workflow_step") or "TALK"),
        "active_scheme": _json_safe(getattr(assistant_response, "active_scheme", None)),
        "active_scheme_code": active_scheme_code,
        "engine_mode": getattr(assistant_response, "engine_mode", "deterministic"),
        "suggested_followups": _json_safe(getattr(assistant_response, "suggested_followups", [])),
        "tool_calls": list(tool_calls or []),
        "data": _json_safe(getattr(assistant_response, "data", None)),
        "eligibility_summary": _json_safe(getattr(assistant_response, "eligibility_summary", None)),
        "checklist_data": _json_safe(getattr(assistant_response, "checklist_data", None)),
        "form_draft_data": _json_safe(getattr(assistant_response, "form_draft_data", None)),
        "confirmation_data": _json_safe(getattr(assistant_response, "confirmation_data", None)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    session["turns"] = turns[-MAX_STORED_TURNS:]
    persist_conversation_state(db, conv_id, current_user, profile, session)


def get_conversation_history_for_user(
    db: Optional[Session],
    conv_id: str,
    current_user: Optional[User],
    profile: Optional[UserProfile] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves stored conversation turns & context state strictly for `current_user` + `conv_id`.
    Returns None if not found or unauthenticated (prevents cross-citizen exposure).
    """
    user_uuid = _get_user_uuid(current_user, profile)
    if not user_uuid or not conv_id:
        return None

    if _can_use_db_table(db):
        try:
            record = db.scalar(
                select(ConversationSession).where(
                    ConversationSession.user_id == user_uuid,
                    ConversationSession.conversation_id == conv_id,
                )
            )
            if record is not None:
                return {
                    "conversation_id": record.conversation_id,
                    "active_scheme_code": record.active_scheme_code,
                    "workflow_step": record.workflow_step,
                    "language": record.language,
                    "state": dict(record.state_data or {}),
                    "turns": list(record.turns or []),
                    "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                }
        except Exception as exc:
            logger.debug("get_conversation_history_for_user DB query failed cleanly: %s", exc)

    if profile and isinstance(getattr(profile, "profile_data", None), dict):
        conv_map = profile.profile_data.get("conversations_by_conv") or {}
        entry = conv_map.get(conv_id)
        if isinstance(entry, dict):
            state = dict(entry.get("state") or {})
            return {
                "conversation_id": conv_id,
                "active_scheme_code": state.get("active_scheme_code"),
                "workflow_step": state.get("workflow_step") or "TALK",
                "language": state.get("language") or "en",
                "state": state,
                "turns": list(entry.get("turns") or []),
                "updated_at": entry.get("updated_at"),
            }

    return None


def list_conversations_for_user(
    db: Optional[Session],
    current_user: Optional[User],
    profile: Optional[UserProfile] = None,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Lists recent persisted conversations belonging strictly to `current_user`."""
    user_uuid = _get_user_uuid(current_user, profile)
    if not user_uuid:
        return []

    if _can_use_db_table(db):
        try:
            records = list(
                db.scalars(
                    select(ConversationSession)
                    .where(ConversationSession.user_id == user_uuid)
                    .order_by(desc(ConversationSession.updated_at))
                    .limit(limit)
                ).all()
            )
            if records:
                return [
                    {
                        "conversation_id": r.conversation_id,
                        "active_scheme_code": r.active_scheme_code,
                        "workflow_step": r.workflow_step,
                        "language": r.language,
                        "turn_count": len(r.turns or []),
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    }
                    for r in records
                ]
        except Exception as exc:
            logger.debug("list_conversations_for_user DB query failed cleanly: %s", exc)

    if profile and isinstance(getattr(profile, "profile_data", None), dict):
        conv_map = profile.profile_data.get("conversations_by_conv") or {}
        items = []
        for cid, entry in conv_map.items():
            if not isinstance(entry, dict):
                continue
            state = entry.get("state") or {}
            items.append({
                "conversation_id": cid,
                "active_scheme_code": state.get("active_scheme_code"),
                "workflow_step": state.get("workflow_step") or "TALK",
                "language": state.get("language") or "en",
                "turn_count": len(entry.get("turns") or []),
                "updated_at": entry.get("updated_at"),
            })
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items[:limit]

    return []
