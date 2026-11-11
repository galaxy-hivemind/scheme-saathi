"""
Pydantic schemas for Scheme Saathi.
"""
from app.schemas.common import APIResponse, APIError, APIErrorDetail
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.profile import (
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
    UserConsentCreate,
    UserConsentRevokeRequest,
    UserConsentResponse,
)
from app.schemas.beneficiary import (
    BeneficiaryRelationship,
    BeneficiaryCreate,
    BeneficiaryUpdate,
    BeneficiaryResponse,
)
from app.schemas.eligibility import (
    TriStateStatus,
    EligibilityResultStatus,
    ConditionResult,
    NextQuestion,
    EligibilityCheckRequest,
    EligibilityEvaluatePathRequest,
    EligibilityResult,
    BatchEligibilityCheckRequest,
    BatchEligibilityResponse,
)

__all__ = [
    "APIResponse",
    "APIError",
    "APIErrorDetail",
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "UserProfileCreate",
    "UserProfileUpdate",
    "UserProfileResponse",
    "UserConsentCreate",
    "UserConsentRevokeRequest",
    "UserConsentResponse",
    "BeneficiaryRelationship",
    "BeneficiaryCreate",
    "BeneficiaryUpdate",
    "BeneficiaryResponse",
    "TriStateStatus",
    "EligibilityResultStatus",
    "ConditionResult",
    "NextQuestion",
    "EligibilityCheckRequest",
    "EligibilityEvaluatePathRequest",
    "EligibilityResult",
    "BatchEligibilityCheckRequest",
    "BatchEligibilityResponse",
]
