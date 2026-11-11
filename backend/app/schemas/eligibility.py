"""
Pydantic schemas for deterministic eligibility evaluation and condition results.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid
from pydantic import BaseModel, Field, ConfigDict


class TriStateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class EligibilityResultStatus(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    POTENTIALLY_ELIGIBLE = "potentially_eligible"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class ConditionResult(BaseModel):
    """Result of evaluating a single condition node against citizen profile."""
    field: str = Field(..., description="Target citizen profile field")
    operator: str = Field(..., description="Operator applied")
    expected_value: Any = Field(..., description="Expected rule threshold or value")
    actual_value: Any = Field(None, description="Actual profile value (or null if missing)")
    status: TriStateStatus = Field(..., description="Tri-state evaluation status (PASS, FAIL, UNKNOWN)")
    passed: Optional[bool] = Field(None, description="True if PASS, False if FAIL, None if UNKNOWN")
    explanation: str = Field(..., description="Human-readable condition evaluation description")


class NextQuestion(BaseModel):
    """Suggested question to resolve an UNKNOWN condition."""
    field: str = Field(..., description="Profile attribute needed")
    question: str = Field(..., description="Human-readable question in English")
    question_hi: Optional[str] = Field(None, description="Human-readable question in Hindi")
    field_type: str = Field(default="boolean", description="Expected data type (boolean, number, string, date)")
    options: Optional[List[str]] = Field(None, description="Permitted options for selection if applicable")


class EligibilityCheckRequest(BaseModel):
    """Request payload for checking eligibility against a specific scheme."""
    scheme_id: uuid.UUID = Field(..., description="UUID of the scheme to evaluate")
    beneficiary_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional UUID of the beneficiary to evaluate (defaults to account holder self profile)",
    )
    profile_override: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional temporary profile attribute overrides for what-if evaluation",
    )


class EligibilityEvaluatePathRequest(BaseModel):
    """Request payload for path-based eligibility evaluation (scheme_id supplied in path)."""
    beneficiary_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional UUID of the beneficiary to evaluate (defaults to account holder self profile)",
    )
    profile_override: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional temporary profile attribute overrides for what-if evaluation",
    )


class EligibilityResult(BaseModel):
    """Comprehensive eligibility evaluation outcome for a scheme."""
    model_config = ConfigDict(from_attributes=True)

    scheme_id: uuid.UUID
    scheme_code: str
    scheme_name: str
    beneficiary_id: Optional[uuid.UUID] = Field(None, description="UUID of the beneficiary evaluated")
    beneficiary_name: Optional[str] = Field(None, description="Full name of the beneficiary evaluated")
    beneficiary_relationship: Optional[str] = Field(None, description="Relationship of beneficiary evaluated ('self', 'father', etc.)")
    overall_status: TriStateStatus
    result: EligibilityResultStatus
    eligible: Optional[bool] = Field(None, description="True if eligible, False if not, None if undetermined")
    rule_version_id: Optional[uuid.UUID] = None
    rule_version: Optional[int] = None
    is_authoritative: bool = Field(default=False, description="True if based on verified statutory guidelines")
    is_provisional: bool = Field(default=True, description="True if based on provisional/incomplete rule criteria")
    criteria_complete: bool = Field(default=False, description="True if all material eligibility rules and statutory exclusions are fully modelled")
    limitations: Optional[str] = Field(None, description="Known statutory limitations or missing sub-rules")
    matched_conditions: List[ConditionResult] = Field(default_factory=list)
    failed_conditions: List[ConditionResult] = Field(default_factory=list)
    unknown_conditions: List[ConditionResult] = Field(default_factory=list)
    condition_results: List[ConditionResult] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    next_questions: List[NextQuestion] = Field(default_factory=list)
    explanation: str
    evaluated_at: datetime


class BatchEligibilityCheckRequest(BaseModel):
    """Request payload for batch eligibility evaluation across schemes."""
    beneficiary_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional UUID of the beneficiary to evaluate across schemes (defaults to self profile)",
    )
    include_pending: bool = Field(
        default=False,
        description="Whether to include schemes with status 'pending_verification'",
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional category filter (e.g. 'agriculture', 'health')",
    )
    profile_override: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional temporary profile attribute overrides",
    )


class BatchEligibilityResponse(BaseModel):
    """Response payload for multi-scheme evaluation."""
    total_evaluated: int
    eligible_count: int
    ineligible_count: int
    unknown_count: int
    results: List[EligibilityResult]

