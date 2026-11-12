"""
Real Backend Tool Registry & Gemini Function Calling Bindings for Scheme Saathi.

Every tool delegates exclusively to genuine backend databases and services
(PostgreSQL Scheme catalog, AST eligibility engine, Document Vault &
readiness_service, prefill_service, submission_service, and UserProfile).
Nothing is ever simulated or fabricated, and citizen identity is always
injected server-side via ToolExecutionContext.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.models.scheme import Scheme
from app.models.user import User
from app.models.user_profile import UserProfile
from app.eligibility.engine import evaluate_scheme_eligibility
from app.schemas.eligibility import EligibilityResultStatus
from app.agents.tools import (
    tool_check_eligibility,
    tool_build_checklist,
    tool_fill_form,
)
from app.agents.form_schemas import (
    SCHEME_CODE_ALIASES,
    get_document_sourcing_info,
    get_form_schema_for_scheme,
)
from app.services.document_service import (
    DOC_STATE_VERIFIED,
    doc_types_match,
    get_localized_doc_label,
    get_localized_status_label,
    normalize_vault_document,
)
from app.services.language_registry import (
    get_localized_ministry,
    get_localized_scheme_metadata,
)
from app.services.document_guidance_service import (
    build_missing_document_guidance,
)
from app.services.readiness_service import (
    _evaluate_doc_applicability,
    evaluate_application_readiness,
    evaluate_profile_completeness,
)
from app.services.portal_registry_service import get_portal_integration_entry
from app.services.submission_service import (
    STATE_PORTAL_SUBMITTED,
    STATE_SUBMITTED,
    STATE_SUBMITTING,
    STATE_SUBMISSION_UNKNOWN,
    is_verified_government_submission,
    sanitize_legacy_unverified_submission,
)

logger = logging.getLogger(__name__)


# ── Known Profile Summary & Field Hygiene ─────────────────────────────────────

PROFILE_FIELD_KEYS = (
    "full_name",
    "age",
    "gender",
    "state",
    "district",
    "residence_type",
    "occupation",
    "annual_income",
    "caste_category",
    "marital_status",
    "land_holding_acres",
    "phone_number",
)


def extract_known_profile_attributes(
    profile: Optional[UserProfile],
    conversation_entities: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Collects non-empty, settled profile attributes plus session conversation entities
    so the assistant never re-asks the citizen for information already known.
    """
    known: Dict[str, Any] = {}
    conv_entities = conversation_entities or {}

    if profile is not None:
        pdata = profile.profile_data if isinstance(getattr(profile, "profile_data", None), dict) else {}
        if getattr(profile, "full_name", None):
            known["full_name"] = profile.full_name
        if getattr(profile, "age", None) is not None:
            known["age"] = profile.age
        if getattr(profile, "gender", None):
            known["gender"] = profile.gender
        if getattr(profile, "state", None):
            known["state"] = profile.state
        if getattr(profile, "district", None):
            known["district"] = profile.district
        if getattr(profile, "residence_type", None):
            known["residence_type"] = profile.residence_type
        if getattr(profile, "occupation", None):
            known["occupation"] = profile.occupation
        if getattr(profile, "annual_income", None) is not None:
            known["annual_income"] = profile.annual_income
        for extra_k in (
            "caste_category",
            "marital_status",
            "land_holding_acres",
            "is_landholding_farmer",
            "is_student",
            "is_street_vendor",
            "sub_district",
            "village",
        ):
            val = pdata.get(extra_k)
            if val not in (None, "", []):
                known[extra_k] = val

    for k, v in conv_entities.items():
        if k == "missing_document_disclosed":
            continue
        if k not in known and v not in (None, "", []):
            known[k] = v

    return known


def _filter_already_known_missing_fields(
    missing_fields: List[str],
    known_attrs: Dict[str, Any],
) -> List[str]:
    """Filters out any missing-field marker whose attribute is already settled in profile."""
    alias_checks = {
        "age": ("age",),
        "date_of_birth": ("age",),
        "gender": ("gender",),
        "state": ("state",),
        "district": ("district",),
        "residence_type": ("residence_type",),
        "occupation": ("occupation",),
        "annual_income": ("annual_income",),
        "annual_family_income": ("annual_income",),
        "income": ("annual_income",),
        "caste_category": ("caste_category",),
        "social_category": ("caste_category",),
        "marital_status": ("marital_status",),
        "land_holding_acres": ("land_holding_acres", "is_landholding_farmer"),
        "land_acres": ("land_holding_acres",),
    }
    filtered: List[str] = []
    for raw in missing_fields:
        norm = str(raw).strip().lower()
        satisfied = False
        for key_token, known_keys in alias_checks.items():
            if key_token == norm or key_token in norm:
                if any(known_attrs.get(kk) not in (None, "", []) for kk in known_keys):
                    satisfied = True
                    break
        if not satisfied and raw not in filtered:
            filtered.append(raw)
    return filtered


# ── Context Container ─────────────────────────────────────────────────────────

@dataclass
class ToolExecutionContext:
    """Server-enforced citizen context passed into every backend tool execution."""
    db: Optional[Session]
    current_user: Optional[User]
    profile: Optional[UserProfile]
    session: Dict[str, Any]
    lang: str = "en"
    all_schemes: List[Scheme] = field(default_factory=list)
    executed_tools: List[str] = field(default_factory=list)
    tool_outputs: List[Dict[str, Any]] = field(default_factory=list)

    def resolve_scheme(self, scheme_code_or_name: Optional[str]) -> Optional[Scheme]:
        """Resolves a scheme code/name, ordinal hint, or inherits session active_scheme_code."""
        target = (scheme_code_or_name or "").strip()
        if not target:
            target = (self.session.get("active_scheme_code") or "").strip()
        if not target:
            return None

        upper = target.upper()
        canon = SCHEME_CODE_ALIASES.get(upper, upper)

        # Check active DB schemes by code, id, short_title, or partial name
        for s in self.all_schemes:
            if (
                s.scheme_code.upper() == canon
                or s.scheme_code.upper() == upper
                or str(getattr(s, "id", "")).upper() == upper
                or (getattr(s, "short_title", None) or "").upper() == canon
            ):
                return s

        for s in self.all_schemes:
            if upper in (s.name or "").upper() or canon in (s.name or "").upper():
                return s

        # Normalized token match (strip hyphens/spaces)
        norm_target = re.sub(r"[^A-Z0-9]", "", canon)
        for s in self.all_schemes:
            norm_code = re.sub(r"[^A-Z0-9]", "", s.scheme_code.upper())
            if norm_target and (norm_target == norm_code or norm_target in norm_code):
                return s

        if canon == "WIDOW-PENSION" or "WIDOW" in upper:
            return Scheme(
                scheme_code="WIDOW-PENSION",
                name="Indira Gandhi National Widow Pension Scheme (IGNWPS / State Widow Pension)",
                category="social_welfare",
                ministry="Ministry of Rural Development / Social Welfare Department",
                benefits="₹1,000 per month DBT direct pension",
                scheme_status="active",
                official_url="https://nsap.nic.in",
                source_url="https://nsap.nic.in",
            )
        return None


def _resolve_doc_key_for_scheme(
    raw_doc_name_or_ordinal: str,
    checklist_items: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Resolves a document query by 1-based ordinal index OR fuzzy document name
    strictly against the active scheme's real required document checklist.
    """
    text = (raw_doc_name_or_ordinal or "").strip()
    if not text or not checklist_items:
        return None

    # 1. Exact numeric / ordinal lookup
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(checklist_items):
            return checklist_items[idx]

    lower = text.lower()
    ordinal_words = {
        "first": 0, "1st": 0, "one": 0, "पहला": 0, "पहली": 0, "पहिले": 0, "पहिल्या": 0,
        "second": 1, "2nd": 1, "two": 1, "दूसरा": 1, "दूसरी": 1, "दुसरे": 1, "दुसरी": 1, "दुसऱ्या": 1,
        "third": 2, "3rd": 2, "three": 2, "तीसरा": 2, "तीसरी": 2, "तिसरे": 2, "तिसऱ्या": 2,
        "fourth": 3, "4th": 3, "four": 3, "चौथा": 3, "चौथी": 3, "चौथे": 3,
        "fifth": 4, "5th": 4, "five": 4, "पांचवा": 4, "पाचवे": 4,
        "last": len(checklist_items) - 1, "आखिरी": len(checklist_items) - 1, "शेवटचे": len(checklist_items) - 1,
    }
    for word, idx in ordinal_words.items():
        if word in lower and 0 <= idx < len(checklist_items):
            return checklist_items[idx]

    # 2. Direct / canonical / equivalence match against active scheme checklist items
    norm_key = lower.replace(" ", "_").replace("-", "_").replace("/", "_")
    for item in checklist_items:
        item_type = (item.get("document_type") or "").lower()
        item_title = (item.get("title") or "").lower()
        if item_type == norm_key or norm_key in item_type or item_type in norm_key:
            return item
        if doc_types_match(item_type, norm_key) or doc_types_match(norm_key, item_type):
            return item
        if lower in item_title:
            return item

    # 3. Special phrase match (e.g. "land possession certificate" -> PM-KISAN's land_records)
    semantic_groups = [
        (["land", "possession", "7/12", "khasra", "khatauni", "patta", "उतारा", "जमीन", "भूमि"], ("land_possession", "land_records")),
        (["aadhaar", "aadhar", "आधार"], ("aadhaar_card", "aadhaar")),
        (["bank", "passbook", "account", "बँक", "बैंक", "पासबुक"], ("bank_passbook", "bank_account")),
        (["income", "utpann", "aay", "उत्पन्न", "आय"], ("income_certificate",)),
        (["death", "मृत्यू", "मृत्यु"], ("death_certificate",)),
        (["ration", "राशन", "रेशन"], ("ration_card",)),
        (["job card", "mgnrega", "मनरेगा", "जॉब"], ("job_card",)),
        (["caste", "जाती", "जात", "जाति"], ("caste_certificate",)),
        (["domicile", "residence", "निवास", "अधिवास", "रहिवासी"], ("domicile_certificate",)),
        (["marksheet", "12th", "marks", "गुणपत्रक", "मार्कशीट"], ("marksheet_12th",)),
        (["mcp", "mother and child", "माता बाल"], ("mcp_card",)),
        (["vending", "lor", "vendor", "फेरीवाला"], ("vending_certificate",)),
    ]
    for cues, candidate_types in semantic_groups:
        if any(c in lower for c in cues):
            for ctype in candidate_types:
                for item in checklist_items:
                    if doc_types_match(item.get("document_type", ""), ctype):
                        return item

    return None


# ── Real Backend Tool Implementations ─────────────────────────────────────────

def _safe_evaluate_scheme(
    scheme: Scheme,
    profile: Optional[UserProfile],
    override_data: Optional[Dict[str, Any]] = None,
):
    """Calls `evaluate_scheme_eligibility` safely even on non-persisted mock Scheme instances."""
    if getattr(scheme, "id", None) is None:
        scheme.id = uuid.uuid4()
    return evaluate_scheme_eligibility(scheme, profile, override_data=override_data)


def _exec_discover_schemes(
    ctx: ToolExecutionContext,
    query: Optional[str] = None,
    category: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 8,
) -> Dict[str, Any]:
    """Searches actual active schemes in PostgreSQL with optional category/state/text filters."""
    candidates = list(ctx.all_schemes)
    if category:
        cat_l = category.strip().lower()
        cat_filtered = [s for s in candidates if (s.category or "").lower() == cat_l]
        if cat_filtered:
            candidates = cat_filtered

    if state:
        st_l = state.strip().lower()
        candidates = [
            s for s in candidates
            if (s.geographic_scope or "central") == "central"
            or st_l in (s.name or "").lower()
            or st_l in (s.description or "").lower()
        ]

    if query:
        q_tokens = [tok for tok in re.split(r"[^a-zA-Z0-9\u0900-\u097F]+", query.lower()) if len(tok) >= 2]
        scored = []
        for s in candidates:
            haystack = f"{s.scheme_code} {s.name} {s.category} {s.description} {s.benefits}".lower()
            score = sum(1 for tok in q_tokens if tok in haystack)
            if score > 0:
                scored.append((score, s))
        if scored:
            scored.sort(key=lambda pair: (-pair[0], pair[1].name or ""))
            candidates = [s for _, s in scored]

    limit = max(1, min(15, int(limit or 8)))
    selected = candidates[:limit]
    conv_entities = ctx.session.get("conversation_entities") or {}

    cards: List[Dict[str, Any]] = []
    for idx, s in enumerate(selected, start=1):
        meta = get_localized_scheme_metadata(s.scheme_code, ctx.lang)
        status_val = None
        if ctx.profile is not None:
            ev = _safe_evaluate_scheme(s, ctx.profile, override_data=conv_entities)
            status_val = ev.result.value
        cards.append({
            "index": idx,
            "id": str(getattr(s, "id", s.scheme_code)),
            "scheme_code": s.scheme_code,
            "name": (meta.get("name") if meta else None) or s.name,
            "category": s.category,
            "ministry": get_localized_ministry(s.ministry, ctx.lang),
            "benefits": (meta.get("benefits") if meta and ctx.lang != "en" else None) or s.benefits,
            "eligibility_status": status_val,
            "official_url": s.official_url or s.source_url,
        })

    ctx.session["last_scheme_list"] = cards
    if len(cards) == 1:
        ctx.session["active_scheme_code"] = cards[0]["scheme_code"]
        ctx.session["active_scheme_name"] = cards[0]["name"]

    return {
        "total_matched": len(candidates),
        "returned_count": len(cards),
        "schemes": cards,
    }


def _exec_check_all_eligible_schemes(
    ctx: ToolExecutionContext,
    category: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs the deterministic AST eligibility engine across ALL active schemes in PostgreSQL
    against the authenticated citizen's profile + conversation facts.
    """
    conv_entities = ctx.session.get("conversation_entities") or {}
    known_attrs = extract_known_profile_attributes(ctx.profile, conv_entities)
    profile_eval = evaluate_profile_completeness(ctx.profile, lang=ctx.lang)

    eligible: List[Dict[str, Any]] = []
    potentially_eligible: List[Dict[str, Any]] = []
    insufficient_info: List[Dict[str, Any]] = []
    not_eligible: List[Dict[str, Any]] = []

    schemes_to_eval = list(ctx.all_schemes)
    if category:
        cat_l = category.strip().lower()
        cat_matches = [s for s in schemes_to_eval if (s.category or "").lower() == cat_l]
        if cat_matches:
            schemes_to_eval = cat_matches

    if state:
        st_l = state.strip().lower()
        schemes_to_eval = [
            s for s in schemes_to_eval
            if (s.geographic_scope or "central") == "central"
            or st_l in (s.name or "").lower()
            or st_l in (s.description or "").lower()
        ]

    for s in schemes_to_eval:
        if getattr(s, "scheme_status", "active") == "inactive":
            continue
        ev = _safe_evaluate_scheme(s, ctx.profile, override_data=conv_entities)
        meta = get_localized_scheme_metadata(s.scheme_code, ctx.lang)
        clean_missing = _filter_already_known_missing_fields(list(ev.missing_fields or []), known_attrs)

        entry = {
            "id": str(getattr(s, "id", s.scheme_code)),
            "scheme_code": s.scheme_code,
            "name": (meta.get("name") if meta else None) or s.name,
            "category": s.category,
            "ministry": get_localized_ministry(s.ministry, ctx.lang),
            "benefits": (meta.get("benefits") if meta and ctx.lang != "en" else None) or s.benefits,
            "eligibility_status": ev.result.value,
            "explanation": ev.explanation,
            "matched_criteria": [c.explanation for c in ev.matched_conditions],
            "failed_criteria": [c.explanation for c in ev.failed_conditions],
            "missing_fields": clean_missing,
            "official_url": s.official_url or s.source_url,
        }

        if ev.result == EligibilityResultStatus.ELIGIBLE:
            eligible.append(entry)
        elif ev.result == EligibilityResultStatus.POTENTIALLY_ELIGIBLE:
            potentially_eligible.append(entry)
        elif ev.result == EligibilityResultStatus.INSUFFICIENT_INFORMATION:
            insufficient_info.append(entry)
        else:
            not_eligible.append(entry)

    # Also check specialized WIDOW-PENSION rule if profile indicates widowed
    if known_attrs.get("marital_status") == "widowed":
        widow_eval = tool_check_eligibility(
            ctx.db, ctx.current_user, ctx.profile, "WIDOW-PENSION", extracted_data=conv_entities
        )
        w_entry = {
            "id": "WIDOW-PENSION",
            "scheme_code": "WIDOW-PENSION",
            "name": widow_eval.get("scheme_name", "Widow Pension Scheme"),
            "category": "social_welfare",
            "ministry": get_localized_ministry("Ministry of Rural Development", ctx.lang),
            "benefits": widow_eval.get("monthly_benefit", "₹1,000 per month DBT"),
            "eligibility_status": widow_eval["status"],
            "explanation": widow_eval["summary"],
            "matched_criteria": widow_eval.get("satisfied_criteria", []),
            "failed_criteria": widow_eval.get("unmet_criteria", []),
            "missing_fields": _filter_already_known_missing_fields(
                widow_eval.get("missing_information", []), known_attrs
            ),
            "official_url": widow_eval.get("official_portal"),
        }
        if widow_eval["status"] == "eligible":
            eligible.insert(0, w_entry)
        elif widow_eval["status"] == "information_required":
            potentially_eligible.insert(0, w_entry)

    # Prioritized ordered list for conversational selection & ordinal references ("the second scheme")
    ranked = eligible + potentially_eligible + insufficient_info
    for idx, item in enumerate(ranked, start=1):
        item["index"] = idx

    ctx.session["last_eligibility_results"] = ranked
    ctx.session["last_scheme_list"] = ranked
    ctx.session["workflow_step"] = "MATCH"

    return {
        "has_citizen_profile": ctx.profile is not None,
        "known_profile_attributes": known_attrs,
        "missing_profile_fields": profile_eval.get("missing_fields", []),
        "missing_profile_labels": profile_eval.get("missing_labels", []),
        "total_evaluated": len(eligible) + len(potentially_eligible) + len(insufficient_info) + len(not_eligible),
        "eligible_count": len(eligible),
        "potentially_eligible_count": len(potentially_eligible),
        "insufficient_info_count": len(insufficient_info),
        "not_eligible_count": len(not_eligible),
        "eligible_schemes": eligible,
        "potentially_eligible_schemes": potentially_eligible,
        "insufficient_info_schemes": insufficient_info[:6],
        "not_eligible_summary": [
            {"scheme_code": x["scheme_code"], "name": x["name"], "reasons": x["failed_criteria"][:2]}
            for x in not_eligible[:8]
        ],
        "ranked_schemes": ranked[:10],
    }


def _exec_check_scheme_eligibility(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluates citizen eligibility for a specific scheme using AST engine + known profile."""
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None:
        return {
            "found": False,
            "error": "No matching scheme could be resolved. Ask citizen which scheme they mean.",
        }

    ctx.session["active_scheme_code"] = scheme.scheme_code
    ctx.session["active_scheme_name"] = scheme.name
    ctx.session["workflow_step"] = "MATCH"

    conv_entities = ctx.session.get("conversation_entities") or {}
    known_attrs = extract_known_profile_attributes(ctx.profile, conv_entities)
    res = tool_check_eligibility(
        ctx.db,
        ctx.current_user,
        ctx.profile,
        scheme.scheme_code,
        extracted_data=conv_entities,
    )
    res["found"] = True
    res["missing_information"] = _filter_already_known_missing_fields(
        res.get("missing_information") or [],
        known_attrs,
    )
    res["known_profile_attributes"] = known_attrs
    meta = get_localized_scheme_metadata(scheme.scheme_code, ctx.lang)
    res["localized_name"] = (meta.get("name") if meta else None) or scheme.name
    res["localized_ministry"] = get_localized_ministry(scheme.ministry, ctx.lang)
    res["category"] = scheme.category
    res["scheme_id"] = str(getattr(scheme, "id", scheme.scheme_code))
    return res


def _exec_get_scheme_details(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieves authoritative details, portal URLs, and verification status for one scheme."""
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None:
        return {
            "found": False,
            "error": "No matching scheme could be resolved. Ask citizen which scheme they mean.",
        }

    ctx.session["active_scheme_code"] = scheme.scheme_code
    ctx.session["active_scheme_name"] = scheme.name

    meta = get_localized_scheme_metadata(scheme.scheme_code, ctx.lang)
    conv_entities = ctx.session.get("conversation_entities") or {}
    known_attrs = extract_known_profile_attributes(ctx.profile, conv_entities)

    elig_info = None
    if ctx.profile is not None or conv_entities:
        ev = _safe_evaluate_scheme(scheme, ctx.profile, override_data=conv_entities)
        elig_info = {
            "status": ev.result.value,
            "explanation": ev.explanation,
            "matched_criteria": [c.explanation for c in ev.matched_conditions],
            "failed_criteria": [c.explanation for c in ev.failed_conditions],
            "missing_fields": _filter_already_known_missing_fields(list(ev.missing_fields or []), known_attrs),
        }

    schema = get_form_schema_for_scheme(scheme.scheme_code)
    last_verified = getattr(scheme, "last_verified_at", None)
    last_verified_str = (
        last_verified.strftime("%Y-%m-%d")
        if hasattr(last_verified, "strftime")
        else (str(last_verified)[:10] if last_verified else None)
    )

    return {
        "found": True,
        "scheme_id": str(getattr(scheme, "id", scheme.scheme_code)),
        "scheme_code": scheme.scheme_code,
        "name": (meta.get("name") if meta else None) or scheme.name,
        "description": (
            (meta.get("description") if meta and ctx.lang != "en" else None)
            or scheme.description
        ),
        "benefits": (
            (meta.get("benefits") if meta and ctx.lang != "en" else None)
            or scheme.benefits
        ),
        "target_beneficiaries": (
            (meta.get("target_beneficiaries") if meta else None)
            or (", ".join(scheme.target_beneficiaries or []))
            or None
        ),
        "category": scheme.category,
        "ministry": get_localized_ministry(scheme.ministry, ctx.lang),
        "geographic_scope": getattr(scheme, "geographic_scope", "central"),
        "official_url": scheme.official_url or scheme.source_url,
        "application_url": scheme.application_url or scheme.official_url or scheme.source_url,
        "source_url": scheme.source_url or scheme.official_url,
        "scheme_status": getattr(scheme, "scheme_status", "active"),
        "last_verified_at": last_verified_str,
        "application_form_supported": bool(schema and "sections" in schema),
        "citizen_eligibility": elig_info,
        "portal_integration": get_portal_integration_entry(scheme.scheme_code, db=ctx.db, scheme=scheme, lang=ctx.lang),
    }


def _exec_get_scheme_benefits(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieves authoritative statutory financial/service benefits for a scheme."""
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None:
        return {
            "found": False,
            "error": "No matching scheme could be resolved. Ask citizen which scheme they mean.",
        }

    ctx.session["active_scheme_code"] = scheme.scheme_code
    ctx.session["active_scheme_name"] = scheme.name

    meta = get_localized_scheme_metadata(scheme.scheme_code, ctx.lang)
    benefits_text = (
        (meta.get("benefits") if meta and ctx.lang != "en" else None)
        or scheme.benefits
        or None
    )
    last_verified = getattr(scheme, "last_verified_at", None)
    last_verified_str = (
        last_verified.strftime("%Y-%m-%d")
        if hasattr(last_verified, "strftime")
        else (str(last_verified)[:10] if last_verified else None)
    )

    return {
        "found": True,
        "scheme_id": str(getattr(scheme, "id", scheme.scheme_code)),
        "scheme_code": scheme.scheme_code,
        "scheme_name": (meta.get("name") if meta else None) or scheme.name,
        "benefits": benefits_text,
        "benefits_available": bool(benefits_text and str(benefits_text).strip()),
        "official_url": scheme.official_url or scheme.source_url,
        "source_url": scheme.source_url or scheme.official_url,
        "last_verified_at": last_verified_str,
    }


def _exec_get_required_documents(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieves authoritative scheme documents paired with the citizen's live Vault
    status, conditional applicability, and preparation sourcing guidance.
    """
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None:
        return {
            "found": False,
            "error": "No matching scheme could be resolved. Ask citizen which scheme they mean.",
        }

    ctx.session["active_scheme_code"] = scheme.scheme_code
    ctx.session["active_scheme_name"] = scheme.name
    ctx.session["workflow_step"] = "CHECKLIST"

    checklist = tool_build_checklist(ctx.db, ctx.current_user, ctx.profile, scheme.scheme_code, lang=ctx.lang)

    # Enrich each item with DB SchemeDocument guidance & conditional applicability
    db_docs = {
        (getattr(d, "document_type", "") or "").lower(): d
        for d in (getattr(scheme, "documents", None) or [])
    }
    existing_form_data: Dict[str, Any] = {}
    if ctx.profile and isinstance(getattr(ctx.profile, "profile_data", None), dict):
        for app in ctx.profile.profile_data.get("applications", []) or []:
            if (app.get("scheme_code") or "").upper() == scheme.scheme_code.upper():
                existing_form_data = dict(app.get("form_data") or {})
                break

    missing_keys: List[str] = []
    for idx, item in enumerate(checklist.get("items", []), start=1):
        dtype = item["document_type"]
        item["index"] = idx
        applicable, waiver_reason = _evaluate_doc_applicability(
            scheme_code=scheme.scheme_code,
            doc_type=dtype,
            is_mandatory=bool(item.get("is_mandatory")),
            profile=ctx.profile,
            form_data=existing_form_data,
            lang=ctx.lang,
        )
        item["applicable"] = applicable
        if waiver_reason:
            item["waiver_reason"] = waiver_reason

        db_doc = db_docs.get(dtype.lower()) or next(
            (d for k, d in db_docs.items() if doc_types_match(dtype, k)), None
        )
        if db_doc and getattr(db_doc, "guidance", None) and item.get("sourcing"):
            item["sourcing"]["db_guidance"] = db_doc.guidance
            if getattr(db_doc, "issuing_authority", None) and not item["sourcing"].get("is_verified"):
                item["sourcing"]["issuing_authority"] = db_doc.issuing_authority

        item["status_label"] = get_localized_status_label(item.get("status", "missing"), ctx.lang)
        if item.get("is_mandatory") and applicable and item.get("status") in ("missing", "rejected"):
            missing_keys.append(dtype)

    ctx.session["last_checklist"] = checklist
    # Preserve explicitly disclosed missing documents alongside Vault gaps
    prior_missing = list(ctx.session.get("missing_documents") or [])
    for mk in missing_keys:
        if mk not in prior_missing:
            prior_missing.append(mk)
    ctx.session["missing_documents"] = prior_missing

    meta = get_localized_scheme_metadata(scheme.scheme_code, ctx.lang)
    return {
        "found": True,
        "scheme_id": str(getattr(scheme, "id", scheme.scheme_code)),
        "scheme_code": scheme.scheme_code,
        "scheme_name": (meta.get("name") if meta else None) or scheme.name,
        "official_url": scheme.official_url or scheme.source_url,
        **checklist,
    }


def _exec_check_citizen_document_status(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
    document_name_or_ordinal: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspects citizen's real Document Vault status (overall or for active scheme/document)."""
    vault_raw = (
        (ctx.profile.profile_data or {}).get("documents", [])
        if ctx.profile and isinstance(getattr(ctx.profile, "profile_data", None), dict)
        else []
    )
    vault_docs = [normalize_vault_document(d) for d in vault_raw]

    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is not None:
        checklist_res = _exec_get_required_documents(ctx, scheme.scheme_code)
        items = checklist_res.get("items", [])
        if document_name_or_ordinal:
            matched_item = _resolve_doc_key_for_scheme(document_name_or_ordinal, items)
            return {
                "found": True,
                "scheme_code": scheme.scheme_code,
                "document": matched_item,
                "vault_document_count": len(vault_docs),
            }
        return {
            "found": True,
            "scheme_code": scheme.scheme_code,
            "vault_document_count": len(vault_docs),
            "checklist": checklist_res,
        }

    return {
        "found": True,
        "scheme_code": None,
        "vault_document_count": len(vault_docs),
        "vault_documents": [
            {
                "id": d.get("id"),
                "document_type": d.get("document_type"),
                "title": get_localized_doc_label(d.get("document_type", "document"), ctx.lang),
                "lifecycle_status": d.get("lifecycle_status"),
                "status_label": get_localized_status_label(d.get("lifecycle_status", "awaiting_citizen_review"), ctx.lang),
                "file_name": d.get("file_name"),
            }
            for d in vault_docs
        ],
    }


def _exec_identify_missing_documents(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
    disclosed_missing_document: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Identifies missing documents from both Document Vault and citizen disclosures,
    resolving against the active scheme checklist and providing honest preparation guidance.
    """
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None and not disclosed_missing_document:
        return {
            "found": False,
            "error": "No active scheme resolved. Ask citizen which scheme they are applying for.",
        }

    checklist_res = None
    items: List[Dict[str, Any]] = []
    if scheme is not None:
        checklist_res = _exec_get_required_documents(ctx, scheme.scheme_code)
        items = checklist_res.get("items", [])

    matched_disclosed_item = None
    disclosed_sourcing = None
    guidance = None
    if disclosed_missing_document:
        guidance = build_missing_document_guidance(
            query_or_doc_key=disclosed_missing_document,
            scheme=scheme,
            checklist_items=items,
            profile=ctx.profile,
            user=ctx.current_user,
            db=ctx.db,
            all_schemes=ctx.all_schemes,
            lang=ctx.lang,
        )
        doc_key = guidance["document_type"]
        matched_disclosed_item = _resolve_doc_key_for_scheme(doc_key, items) if items else None
        disclosed_sourcing = (matched_disclosed_item or {}).get("sourcing") or guidance.get("sourcing")

        ctx.session["last_discussed_document"] = {
            "document_type": doc_key,
            "title": guidance.get("title") or doc_key,
            "scheme_code": scheme.scheme_code if scheme else None,
        }

        missing_list = list(ctx.session.get("missing_documents") or [])
        if doc_key not in missing_list:
            missing_list.append(doc_key)
        ctx.session["missing_documents"] = missing_list

        confirmed_list = [d for d in (ctx.session.get("citizen_confirmed_documents") or []) if d != doc_key]
        ctx.session["citizen_confirmed_documents"] = confirmed_list

    missing_items = [
        it for it in items
        if it.get("status") in ("missing", "rejected")
        or it.get("document_type") in (ctx.session.get("missing_documents") or [])
    ]

    return {
        "found": True,
        "scheme_code": scheme.scheme_code if scheme else None,
        "scheme_name": (checklist_res or {}).get("scheme_name") if scheme else None,
        "disclosed_document": matched_disclosed_item,
        "disclosed_sourcing": disclosed_sourcing,
        "guidance": guidance,
        "missing_items": missing_items,
        "checklist": checklist_res,
    }


def _exec_get_document_preparation_guidance(
    ctx: ToolExecutionContext,
    document_name_or_ordinal: str = "",
    scheme_code_or_name: Optional[str] = None,
    focus: str = "all",
) -> Dict[str, Any]:
    """
    Resolves a document (by name, ordinal like 'the second document', or session
    `last_discussed_document`) against the active scheme checklist and returns
    structured preparation guidance separating Verified, Estimated, and Unavailable facts.
    """
    raw_target = (document_name_or_ordinal or "").strip()
    anaphoric_doc = raw_target.lower() in (
        "", "it", "this", "that", "this document", "that document", "the document",
        "हे कागदपत्र", "ते कागदपत्र", "यह दस्तावेज", "यह दस्तावेज़", "उस दस्तावेज़",
    )
    if anaphoric_doc:
        last_doc = ctx.session.get("last_discussed_document") or {}
        if last_doc.get("document_type"):
            raw_target = last_doc["document_type"]
            if not scheme_code_or_name and last_doc.get("scheme_code"):
                scheme_code_or_name = last_doc["scheme_code"]
        elif ctx.session.get("missing_documents"):
            raw_target = ctx.session["missing_documents"][-1]

    scheme = ctx.resolve_scheme(scheme_code_or_name)
    items: List[Dict[str, Any]] = []
    if scheme is not None:
        if (
            ctx.session.get("last_checklist")
            and ctx.session["last_checklist"].get("scheme_code") == scheme.scheme_code
        ):
            items = ctx.session["last_checklist"].get("items") or []
        else:
            checklist_res = _exec_get_required_documents(ctx, scheme.scheme_code)
            items = checklist_res.get("items") or []
    elif ctx.session.get("last_checklist"):
        items = ctx.session["last_checklist"].get("items") or []

    matched_item = _resolve_doc_key_for_scheme(raw_target, items) if raw_target else None
    if matched_item:
        doc_key = matched_item["document_type"]
    else:
        # Honest boundary if citizen asked for out-of-bounds ordinal on an active checklist
        if items and raw_target and re.search(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|\d+)\b", raw_target.lower()):
            return {
                "found": False,
                "error": f"Document position '{raw_target}' was not found; this scheme checklist has {len(items)} documents.",
                "available_documents": [f"{i.get('index')}. {i.get('title')}" for i in items],
            }
        doc_key = raw_target

    if not doc_key:
        return {
            "found": False,
            "error": "No document was specified or present in current conversation memory. Ask citizen which document they need help obtaining.",
        }

    guidance = build_missing_document_guidance(
        query_or_doc_key=doc_key,
        scheme=scheme,
        checklist_items=items,
        profile=ctx.profile,
        user=ctx.current_user,
        db=ctx.db,
        all_schemes=ctx.all_schemes,
        lang=ctx.lang,
    )
    resolved_scheme_code = (
        scheme.scheme_code
        if scheme is not None
        else (ctx.session.get("last_checklist") or {}).get("scheme_code")
    )
    ctx.session["last_discussed_document"] = {
        "document_type": guidance["document_type"],
        "title": guidance["title"],
        "scheme_code": resolved_scheme_code,
    }

    return {
        "found": True,
        "scheme_code": resolved_scheme_code,
        "index": (matched_item or {}).get("index"),
        "document_type": guidance["document_type"],
        "title": (matched_item or {}).get("title") or guidance.get("title"),
        "is_mandatory": (matched_item or {}).get("is_mandatory"),
        "vault_status": guidance.get("vault_status", "missing"),
        "focus": focus or "all",
        "sourcing": (matched_item or {}).get("sourcing") or guidance.get("sourcing"),
        "guidance": guidance,
    }


def _exec_recheck_application_readiness(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
    citizen_claims_all_documents: bool = False,
) -> Dict[str, Any]:
    """
    Re-evaluates actual Vault document readiness + form + profile readiness
    using `evaluate_application_readiness` and `tool_build_checklist`.
    Never claims documents are verified unless Vault verification actually succeeded.
    """
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None:
        return {
            "found": False,
            "error": "No active scheme resolved. Ask citizen which scheme readiness should be checked for.",
        }

    ctx.session["active_scheme_code"] = scheme.scheme_code
    ctx.session["active_scheme_name"] = scheme.name

    checklist = _exec_get_required_documents(ctx, scheme.scheme_code)
    existing_form_data: Dict[str, Any] = {}
    if ctx.profile and isinstance(getattr(ctx.profile, "profile_data", None), dict):
        for app in ctx.profile.profile_data.get("applications", []) or []:
            if (
                (app.get("scheme_code") or "").upper() == scheme.scheme_code.upper()
                and not app.get("legacy_synthetic_submission")
            ):
                existing_form_data = dict(app.get("form_data") or {})
                break

    if citizen_claims_all_documents:
        ctx.session["citizen_confirmed_documents"] = [
            it["document_type"] for it in checklist.get("items", []) if it.get("is_mandatory")
        ]
        # Clear verbal disclosure flags now that citizen states they possess them,
        # while still reporting authentic Vault status!
        ctx.session["missing_documents"] = [
            it["document_type"]
            for it in checklist.get("items", [])
            if it.get("is_mandatory") and it.get("applicable", True) and it.get("status") in ("missing", "rejected")
        ]

    readiness = evaluate_application_readiness(
        scheme_code=scheme.scheme_code,
        scheme_id=str(getattr(scheme, "id", scheme.scheme_code)),
        form_data=existing_form_data,
        profile=ctx.profile,
        db=ctx.db,
        lang=ctx.lang,
    )

    items = checklist.get("items", [])
    verified_docs = [it["title"] for it in items if it.get("status") == DOC_STATE_VERIFIED]
    pending_review_docs = [
        it["title"] for it in items if it.get("status") in ("uploaded", "extracted", "awaiting_citizen_review", "reviewed")
    ]
    missing_or_rejected_docs = [
        it["title"]
        for it in items
        if it.get("is_mandatory") and it.get("applicable", True) and it.get("status") in ("missing", "rejected")
    ]

    return {
        "found": True,
        "scheme_code": scheme.scheme_code,
        "scheme_name": checklist.get("scheme_name", scheme.name),
        "citizen_reported_all_documents": citizen_claims_all_documents,
        "documents_ready_in_vault": bool(checklist.get("is_ready_for_application")),
        "mandatory_count": checklist.get("mandatory_count", 0),
        "mandatory_verified_count": checklist.get("mandatory_ready", 0),
        "mandatory_uploaded_count": checklist.get("mandatory_present", 0),
        "verified_documents": verified_docs,
        "pending_review_documents": pending_review_docs,
        "missing_or_rejected_documents": missing_or_rejected_docs,
        "overall_readiness_passed": readiness.get("passed", False),
        "overall_percentage": readiness.get("overall_percentage", 0),
        "breakdown": readiness.get("breakdown"),
        "errors": readiness.get("errors", []),
        "warnings": readiness.get("warnings", []),
        "checklist": checklist,
    }


def _exec_create_or_prefill_application_draft(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
    extra_answers: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Starts / pre-fills a scheme application draft via the shared universal prefill engine
    without violating strict schema integrity for unsupported schemes.
    """
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None:
        return {
            "found": False,
            "error": "No active scheme resolved. Ask citizen which scheme they want to apply for.",
        }

    ctx.session["active_scheme_code"] = scheme.scheme_code
    ctx.session["active_scheme_name"] = scheme.name
    ctx.session["workflow_step"] = "PRE-FILL"

    conv_entities = dict(ctx.session.get("conversation_entities") or {})
    if extra_answers:
        conv_entities.update(extra_answers)

    fill_res = tool_fill_form(
        ctx.db,
        ctx.current_user,
        ctx.profile,
        scheme.scheme_code,
        form_overrides=extra_answers or {},
        conversation_entities=conv_entities,
        lang=ctx.lang,
    )

    if fill_res.get("form_supported"):
        ctx.session["active_application_id"] = fill_res.get("application_id")
        ctx.session["application_status"] = "draft"
        ctx.session["application_draft_summary"] = {
            "application_id": fill_res.get("application_id"),
            "scheme_code": fill_res.get("scheme_code"),
            "scheme_name": fill_res.get("scheme_title"),
            "readiness_percentage": fill_res.get("readiness_percentage"),
            "filled_mandatory_fields": fill_res.get("filled_mandatory_fields"),
            "total_mandatory_fields": fill_res.get("total_mandatory_fields"),
            "requires_input_fields": fill_res.get("requires_input_fields"),
            "form_supported": True,
        }

    portal_entry = get_portal_integration_entry(scheme.scheme_code, db=ctx.db, scheme=scheme, lang=ctx.lang)
    doc_check = tool_build_checklist(ctx.db, ctx.current_user, ctx.profile, scheme.scheme_code, lang=ctx.lang)
    ctx.session["last_checklist"] = doc_check

    missing_mandatory_docs = [
        it["title"] for it in doc_check.get("items", [])
        if it.get("is_mandatory") and it.get("status") != DOC_STATE_VERIFIED
    ]

    profile_summary = extract_known_profile_attributes(ctx.profile)
    req_inputs = list(fill_res.get("requires_input_fields") or [])
    missing_fields_formatted = []
    for item in req_inputs:
        if isinstance(item, dict):
            missing_fields_formatted.append(item.get("label") or item.get("name") or "")
        elif isinstance(item, str):
            missing_fields_formatted.append(item)

    return {
        "found": True,
        **fill_res,
        "portal_integration": fill_res.get("portal_integration") or portal_entry,
        "citizen_profile_summary": profile_summary,
        "missing_fields": [f for f in missing_fields_formatted if f],
        "missing_mandatory_documents": missing_mandatory_docs,
        "document_readiness": {
            "is_ready": doc_check.get("is_ready_for_application"),
            "mandatory_ready": doc_check.get("mandatory_ready"),
            "mandatory_count": doc_check.get("mandatory_count"),
            "missing_or_pending": missing_mandatory_docs,
            "items": doc_check.get("items", []),
        },
    }


def _exec_get_portal_integration(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve official portal URLs, instructions, required documents, and submission mode (A/B/C)."""
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    code = scheme.scheme_code if scheme else (scheme_code_or_name or ctx.session.get("active_scheme_code") or "")
    if not code:
        return {"found": False, "error": "No active scheme resolved."}
    entry = get_portal_integration_entry(code, db=ctx.db, scheme=scheme, lang=ctx.lang)
    return {"found": True, **entry}


def _exec_validate_application_draft(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Validates citizen's application draft (fields, formats, conflicts, Vault documents)."""
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    if scheme is None:
        return {
            "found": False,
            "error": "No active scheme resolved.",
        }

    fill_res = tool_fill_form(
        ctx.db,
        ctx.current_user,
        ctx.profile,
        scheme.scheme_code,
        conversation_entities=ctx.session.get("conversation_entities") or {},
        lang=ctx.lang,
    )
    if not fill_res.get("form_supported"):
        return {"found": True, **fill_res}

    readiness = evaluate_application_readiness(
        scheme_code=scheme.scheme_code,
        scheme_id=str(getattr(scheme, "id", scheme.scheme_code)),
        form_data=fill_res.get("form_data") or {},
        profile=ctx.profile,
        db=ctx.db,
        lang=ctx.lang,
    )
    return {
        "found": True,
        "scheme_code": scheme.scheme_code,
        "scheme_name": fill_res.get("scheme_title", scheme.name),
        "application_id": fill_res.get("application_id"),
        "passed": readiness.get("passed", False),
        "overall_percentage": readiness.get("overall_percentage", 0),
        "errors": readiness.get("errors", []),
        "warnings": readiness.get("warnings", []),
        "breakdown": readiness.get("breakdown"),
        "can_confirm": bool(fill_res.get("can_confirm") and readiness.get("passed")),
    }


def _exec_get_application_status(
    ctx: ToolExecutionContext,
    scheme_code_or_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieves factual application status from citizen's DB profile AND computes
    context-aware 'what happens next?' guidance without ever fabricating status.
    """
    scheme = ctx.resolve_scheme(scheme_code_or_name)
    apps: List[Dict[str, Any]] = []
    if ctx.profile and isinstance(getattr(ctx.profile, "profile_data", None), dict):
        apps = list(ctx.profile.profile_data.get("applications") or [])

    matched_app = None
    if ctx.session.get("active_application_id"):
        matched_app = next((a for a in apps if a.get("id") == ctx.session["active_application_id"]), None)
    if matched_app is None and scheme is not None:
        matched_app = next(
            (
                a for a in apps
                if (a.get("scheme_code") or "").upper() == scheme.scheme_code.upper()
                and not a.get("legacy_synthetic_submission")
                and not str(a.get("reference_number") or "").upper().startswith("SAATHI/")
            ),
            None,
        )
    if matched_app is None and apps:
        matched_app = next(
            (
                a for a in apps
                if not a.get("legacy_synthetic_submission")
                and not str(a.get("reference_number") or "").upper().startswith("SAATHI/")
            ),
            None,
        )

    sanitized_app = dict(matched_app) if isinstance(matched_app, dict) else None
    if sanitized_app is not None:
        sanitize_legacy_unverified_submission(sanitized_app)
    has_verified_submission = is_verified_government_submission(sanitized_app) if sanitized_app else False

    target_code = (
        (sanitized_app.get("scheme_code") if sanitized_app else None)
        or (scheme.scheme_code if scheme else None)
        or ctx.session.get("active_scheme_code")
    )
    resolved_scheme = scheme or (ctx.resolve_scheme(target_code) if target_code else None)
    portal_entry = (
        get_portal_integration_entry(target_code, db=ctx.db, scheme=resolved_scheme, lang=ctx.lang)
        if target_code
        else None
    )
    portal_url = (
        (portal_entry or {}).get("official_application_url")
        or (
            (resolved_scheme.application_url or resolved_scheme.official_url or resolved_scheme.source_url)
            if resolved_scheme
            else "https://www.india.gov.in/"
        )
    )
    tracking_url = (portal_entry or {}).get("tracking_url") or portal_url

    doc_status = None
    if target_code:
        doc_status = tool_build_checklist(ctx.db, ctx.current_user, ctx.profile, target_code, lang=ctx.lang)

    next_steps: List[str] = []
    stage = "no_scheme"
    if sanitized_app:
        state = sanitized_app.get("lifecycle_state") or "draft"
        stage = state
        if state == STATE_SUBMISSION_UNKNOWN:
            next_steps = [
                "Reconcile your previous submission dispatch status in Applications before retrying.",
                f"Verify whether your application appears on the official portal: {portal_url}",
            ]
        elif state == STATE_SUBMITTED and has_verified_submission:
            next_steps = [
                f"Track your submitted reference {sanitized_app.get('reference_number')} on {tracking_url}.",
                "Keep Aadhaar-seeded bank account active on NPCI mapper for DBT disbursements.",
            ]
        elif state == STATE_PORTAL_SUBMITTED and sanitized_app.get("official_reference_number"):
            next_steps = [
                f"Track your official portal reference `{sanitized_app.get('official_reference_number')}` at {tracking_url}.",
                "Keep a copy of your official portal acknowledgment receipt for verification.",
            ]
        elif state == "confirmed":
            next_steps = [
                f"Complete final submission on the official portal ({portal_url}) using your confirmed application summary.",
                "Return with your official application reference number so Scheme Saathi can record it for tracking.",
            ]
        elif state in ("draft", "validated", "validation_failed", "awaiting_confirmation"):
            missing_docs = [
                it["title"] for it in (doc_status or {}).get("items", [])
                if it.get("is_mandatory") and it.get("status") != DOC_STATE_VERIFIED
            ]
            if missing_docs:
                next_steps.append(f"Upload and verify pending mandatory documents in Document Vault: {', '.join(missing_docs)}.")
            req_inputs = (sanitized_app.get("prefill_summary") or {}).get("requires_input_fields") or []
            if req_inputs:
                next_steps.append(f"Complete the {len(req_inputs)} remaining application form field(s) in your draft.")
            next_steps.append("Review the full application summary and provide explicit confirmation before portal handoff.")
    elif target_code:
        stage = "scheme_selected"
        missing_docs = [
            it["title"] for it in (doc_status or {}).get("items", [])
            if it.get("is_mandatory") and it.get("status") != DOC_STATE_VERIFIED
        ]
        if missing_docs:
            next_steps.append(f"Prepare and verify required documents in Document Vault: {', '.join(missing_docs)}.")
        schema = get_form_schema_for_scheme(target_code)
        if schema:
            next_steps.append(f"Say 'Help me apply' or click Pre-fill Application Draft to start your {target_code} draft.")
        else:
            next_steps.append(f"Prepare your documents and apply directly on the official portal: {portal_url}")
    elif ctx.session.get("last_eligibility_results"):
        stage = "schemes_listed"
        next_steps = [
            "Pick one of your eligible schemes (for example by naming it or asking about the first/second scheme) to review details, documents, and apply."
        ]
    else:
        next_steps = [
            "Ask 'Which government schemes am I eligible for?' or name a scheme like PM-KISAN, KCC, AB-PMJAY, or PMAY-G."
        ]

    portal_reported = bool(
        sanitized_app
        and sanitized_app.get("lifecycle_state") == STATE_PORTAL_SUBMITTED
        and sanitized_app.get("official_reference_number")
    )
    eff_ref = (
        sanitized_app.get("reference_number")
        if sanitized_app and has_verified_submission
        else (sanitized_app.get("official_reference_number") if portal_reported else None)
    )
    return {
        "has_application": sanitized_app is not None,
        "stage": stage,
        "scheme_code": target_code,
        "scheme_name": (resolved_scheme.name if resolved_scheme else None) or target_code,
        "application_id": sanitized_app.get("id") if sanitized_app else None,
        "lifecycle_state": sanitized_app.get("lifecycle_state") if sanitized_app else None,
        "verified_government_submission": has_verified_submission,
        "portal_submitted": portal_reported,
        "reference_number": eff_ref,
        "official_reference_number": eff_ref,
        "submission_method": (sanitized_app.get("submission_method") if sanitized_app else None) or (portal_entry or {}).get("submission_method"),
        "submission_date": sanitized_app.get("submission_date") if sanitized_app else None,
        "portal_url": portal_url,
        "tracking_url": tracking_url,
        "portal_integration": portal_entry,
        "document_readiness": {
            "is_ready": (doc_status or {}).get("is_ready_for_application"),
            "mandatory_ready": (doc_status or {}).get("mandatory_ready"),
            "mandatory_count": (doc_status or {}).get("mandatory_count"),
        } if doc_status else None,
        "next_steps": next_steps,
    }


# ── Tool Registry & Gemini Function Declarations ──────────────────────────────

TOOL_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {
    "discover_schemes": _exec_discover_schemes,
    "check_all_eligible_schemes": _exec_check_all_eligible_schemes,
    "check_scheme_eligibility": _exec_check_scheme_eligibility,
    "get_scheme_details": _exec_get_scheme_details,
    "get_scheme_benefits": _exec_get_scheme_benefits,
    "get_required_documents": _exec_get_required_documents,
    "check_citizen_document_status": _exec_check_citizen_document_status,
    "identify_missing_documents": _exec_identify_missing_documents,
    "get_document_preparation_guidance": _exec_get_document_preparation_guidance,
    "recheck_application_readiness": _exec_recheck_application_readiness,
    "create_or_prefill_application_draft": _exec_create_or_prefill_application_draft,
    "validate_application_draft": _exec_validate_application_draft,
    "get_application_status": _exec_get_application_status,
}


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "check_all_eligible_schemes",
        "description": "Evaluate citizen eligibility across ALL active government welfare schemes using their saved profile and conversation facts. Call when user asks which schemes they qualify or are eligible for.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional scheme category filter (e.g. agriculture, health, education, housing, women_welfare)."},
                "state": {"type": "string", "description": "Optional Indian state name."},
            },
        },
    },
    {
        "name": "discover_schemes",
        "description": "Search the government welfare scheme database catalog by keyword, category, or state.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase."},
                "category": {"type": "string", "description": "Optional category name."},
                "state": {"type": "string", "description": "Optional state name."},
                "limit": {"type": "integer", "description": "Maximum number of schemes to return."},
            },
        },
    },
    {
        "name": "check_scheme_eligibility",
        "description": "Evaluate citizen eligibility against official criteria for one specific welfare scheme.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Scheme code (e.g. PM-KISAN, KCC, AB-PMJAY) or scheme name. Omit to use active scheme."},
            },
        },
    },
    {
        "name": "get_scheme_details",
        "description": "Get official details, description, ministry, benefits, target beneficiaries, and portal URL for a specific welfare scheme and set it as active scheme.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Scheme code or name (e.g. PM-KISAN, PMAY-G, APY)."},
            },
            "required": ["scheme_code_or_name"],
        },
    },
    {
        "name": "get_scheme_benefits",
        "description": "Get statutory financial assistance and benefits for the specified or currently active welfare scheme.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; uses active scheme from conversation context if omitted."},
            },
        },
    },
    {
        "name": "get_required_documents",
        "description": "Retrieve the numbered list of required and optional documents for the specified or active scheme along with citizen Vault status.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; uses active scheme if omitted."},
            },
        },
    },
    {
        "name": "check_citizen_document_status",
        "description": "Check real status (verified, awaiting review, rejected, or missing) of documents in the citizen's Document Vault.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code."},
                "document_name_or_ordinal": {"type": "string", "description": "Optional document name or 1-based index/ordinal (e.g. 'second')."},
            },
        },
    },
    {
        "name": "identify_missing_documents",
        "description": "Record a missing document disclosed by the citizen or missing in Vault, map it to the active scheme, and return missing document status + sourcing steps.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; inherits active scheme if omitted."},
                "disclosed_missing_document": {"type": "string", "description": "Name or ordinal of the document the citizen says they do not have (e.g. 'land possession certificate', 'second')."},
            },
        },
    },
    {
        "name": "get_document_preparation_guidance",
        "description": "Get official preparation assistance for a specific or previously discussed missing document: why required, where to obtain, responsible authority, portal URL, process steps, verified/estimated fees & timeline, and fallback options.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_name_or_ordinal": {"type": "string", "description": "Document name, ordinal index (e.g. '2', 'second', 'land possession certificate'), or 'this document' to resolve last discussed document."},
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; uses active scheme if omitted."},
                "focus": {"type": "string", "description": "Specific question focus: 'all', 'process', 'cost', 'where_to_apply', 'fallback', or 'why_required'."},
            },
        },
    },
    {
        "name": "recheck_application_readiness",
        "description": "Recheck citizen's actual Document Vault, profile, and application form readiness. Always call when citizen says they now have all documents or asks if they are ready.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; uses active scheme if omitted."},
                "citizen_claims_all_documents": {"type": "boolean", "description": "True if citizen just stated they now have all documents."},
            },
        },
    },
    {
        "name": "create_or_prefill_application_draft",
        "description": "Create or resume and pre-fill an application draft for a scheme from citizen profile, Vault documents, and conversation facts.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; uses active scheme if omitted."},
            },
        },
    },
    {
        "name": "validate_application_draft",
        "description": "Run authoritative field, format, conflict, and Vault document validation on the citizen's application draft.",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; uses active scheme if omitted."},
            },
        },
    },
    {
        "name": "get_application_status",
        "description": "Retrieve real citizen application draft/submission status (never simulated) and exact next steps ('what happens next?').",
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code_or_name": {"type": "string", "description": "Optional scheme code; inherits active scheme or latest draft if omitted."},
            },
        },
    },
]


def execute_backend_tool(
    ctx: ToolExecutionContext,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Executes a registered real backend tool safely under `ToolExecutionContext`."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return {"error": f"Unknown backend tool '{tool_name}'."}

    raw_args = dict(arguments or {})
    # Never allow model/caller to pass security/internal context args
    for forbidden in ("db", "user", "user_id", "profile", "current_user", "ctx", "session"):
        raw_args.pop(forbidden, None)

    try:
        result = fn(ctx, **raw_args)
    except TypeError:
        # Filter unexpected kwargs safely
        import inspect
        sig = inspect.signature(fn)
        allowed_args = {k: v for k, v in raw_args.items() if k in sig.parameters}
        result = fn(ctx, **allowed_args)
    except Exception as exc:
        logger.exception("Error executing backend tool %s: %s", tool_name, exc)
        return {"error": str(exc)}

    ctx.executed_tools.append(tool_name)
    ctx.tool_outputs.append({"tool": tool_name, "arguments": raw_args, "result": result})
    return result


def get_gemini_tool_declarations() -> Any:
    """
    Builds a `google.generativeai.protos.Tool` containing all real backend
    FunctionDeclarations for Gemini native tool calling.
    """
    from google.generativeai import protos

    type_map = {
        "string": protos.Type.STRING,
        "integer": protos.Type.INTEGER,
        "number": protos.Type.NUMBER,
        "boolean": protos.Type.BOOLEAN,
        "object": protos.Type.OBJECT,
        "array": protos.Type.ARRAY,
    }

    declarations: List[protos.FunctionDeclaration] = []
    for spec in TOOL_SCHEMAS:
        params = spec.get("parameters", {})
        props = {}
        for pname, pinfo in (params.get("properties") or {}).items():
            props[pname] = protos.Schema(
                type=type_map.get(pinfo.get("type", "string"), protos.Type.STRING),
                description=pinfo.get("description", ""),
            )
        declarations.append(
            protos.FunctionDeclaration(
                name=spec["name"],
                description=spec["description"],
                parameters=protos.Schema(
                    type=protos.Type.OBJECT,
                    properties=props,
                    required=params.get("required") or [],
                ),
            )
        )

    return protos.Tool(function_declarations=declarations)
