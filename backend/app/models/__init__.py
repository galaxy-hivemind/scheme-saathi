"""
SQLAlchemy database models for Scheme Saathi.
"""
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.user_consent import UserConsent
from app.models.beneficiary_profile import BeneficiaryProfile
from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.scheme_document import SchemeDocument

__all__ = [
    "User",
    "UserProfile",
    "UserConsent",
    "BeneficiaryProfile",
    "Scheme",
    "SchemeRuleVersion",
    "SchemeDocument",
]
