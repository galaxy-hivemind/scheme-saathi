"""
Eligibility evaluation package for Scheme Saathi.
Provides deterministic tri-state AST evaluation, strict operators, and next-question generation.
"""
from app.eligibility.operators import evaluate_operator, parse_strict_bool, OPERATORS
from app.eligibility.engine import (
    evaluate_scheme_eligibility,
    evaluate_ast,
    evaluate_condition_node,
    extract_profile_field,
    get_next_question,
)

__all__ = [
    "evaluate_operator",
    "parse_strict_bool",
    "OPERATORS",
    "evaluate_scheme_eligibility",
    "evaluate_ast",
    "evaluate_condition_node",
    "extract_profile_field",
    "get_next_question",
]
