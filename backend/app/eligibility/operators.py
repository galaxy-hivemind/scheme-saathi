"""
Deterministic eligibility rule operators and type-safe evaluation.
Pure Python implementation with no eval, exec, or external expression engines.
"""
from typing import Any, Callable, Dict, List
from decimal import Decimal, InvalidOperation
from datetime import date, datetime


def _to_decimal(val: Any) -> Decimal:
    """Safely convert numeric or string values to Decimal for precise comparison."""
    if isinstance(val, bool):
        raise ValueError(f"Cannot convert boolean value '{val}' to numeric Decimal")
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    if isinstance(val, str):
        try:
            return Decimal(val.strip())
        except InvalidOperation:
            raise ValueError(f"Cannot convert string '{val}' to numeric Decimal")
    raise ValueError(f"Cannot convert value of type {type(val)} to Decimal")


def _to_date(val: Any) -> date:
    """Safely convert ISO date string or date/datetime to date."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return date.fromisoformat(val.strip().split("T")[0])
        except Exception:
            raise ValueError(f"Cannot convert string '{val}' to date")
    raise ValueError(f"Cannot convert value of type {type(val)} to date")


def op_equals(actual: Any, expected: Any) -> bool:
    """Compare equality with case-insensitivity for strings, booleans, and numeric coercion."""
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False

    # Boolean comparison (handles bool vs bool and bool vs string representation)
    if isinstance(actual, bool) or isinstance(expected, bool):
        if isinstance(actual, bool) and isinstance(expected, bool):
            return actual is expected
        if isinstance(actual, str):
            actual_bool = actual.strip().lower() in ("true", "1", "yes")
            return actual_bool is expected
        if isinstance(expected, str):
            expected_bool = expected.strip().lower() in ("true", "1", "yes")
            return actual is expected_bool
        return False

    # String comparison
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().lower() == expected.strip().lower()

    # Numeric comparison
    try:
        return _to_decimal(actual) == _to_decimal(expected)
    except (ValueError, TypeError, InvalidOperation):
        pass

    # Date comparison
    if isinstance(actual, (date, datetime)) or isinstance(expected, (date, datetime)):
        try:
            return _to_date(actual) == _to_date(expected)
        except Exception:
            pass

    return actual == expected


def op_not_equals(actual: Any, expected: Any) -> bool:
    """Compare inequality."""
    return not op_equals(actual, expected)


def op_greater_than(actual: Any, expected: Any) -> bool:
    """Check if actual > expected with numeric or date comparison."""
    if actual is None or expected is None:
        raise ValueError("Cannot perform greater_than comparison on null value")
    if isinstance(actual, (date, datetime)) or isinstance(expected, (date, datetime)):
        return _to_date(actual) > _to_date(expected)
    return _to_decimal(actual) > _to_decimal(expected)


def op_greater_than_or_equal(actual: Any, expected: Any) -> bool:
    """Check if actual >= expected with numeric or date comparison."""
    if actual is None or expected is None:
        raise ValueError("Cannot perform greater_than_or_equal comparison on null value")
    if isinstance(actual, (date, datetime)) or isinstance(expected, (date, datetime)):
        return _to_date(actual) >= _to_date(expected)
    return _to_decimal(actual) >= _to_decimal(expected)


def op_less_than(actual: Any, expected: Any) -> bool:
    """Check if actual < expected with numeric or date comparison."""
    if actual is None or expected is None:
        raise ValueError("Cannot perform less_than comparison on null value")
    if isinstance(actual, (date, datetime)) or isinstance(expected, (date, datetime)):
        return _to_date(actual) < _to_date(expected)
    return _to_decimal(actual) < _to_decimal(expected)


def op_less_than_or_equal(actual: Any, expected: Any) -> bool:
    """Check if actual <= expected with numeric or date comparison."""
    if actual is None or expected is None:
        raise ValueError("Cannot perform less_than_or_equal comparison on null value")
    if isinstance(actual, (date, datetime)) or isinstance(expected, (date, datetime)):
        return _to_date(actual) <= _to_date(expected)
    return _to_decimal(actual) <= _to_decimal(expected)


def op_in(actual: Any, expected: Any) -> bool:
    """Check if actual value is present in expected list/set."""
    if actual is None:
        return False
    if not isinstance(expected, (list, tuple, set)):
        raise ValueError(f"Operator 'in' requires expected value to be list, tuple, or set, got {type(expected)}")
    if isinstance(actual, str):
        actual_norm = actual.strip().lower()
        return any(
            actual_norm == (item.strip().lower() if isinstance(item, str) else item)
            for item in expected
        )
    return actual in expected


def op_not_in(actual: Any, expected: Any) -> bool:
    """Check if actual value is not present in expected list/set."""
    return not op_in(actual, expected)


def op_exists(actual: Any, expected: Any) -> bool:
    """Check whether field exists / is non-null. Expected is a boolean."""
    expected_bool = bool(expected)
    actual_exists = actual is not None
    return actual_exists == expected_bool


def op_contains(actual: Any, expected: Any) -> bool:
    """Check if actual list or string contains expected item/substring."""
    if actual is None or expected is None:
        return False
    if isinstance(actual, str) and isinstance(expected, str):
        return expected.strip().lower() in actual.strip().lower()
    if isinstance(actual, (list, tuple, set)):
        return op_in(expected, actual)
    raise ValueError(f"Operator 'contains' requires actual value to be string or collection, got {type(actual)}")


OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
    "equals": op_equals,
    "not_equals": op_not_equals,
    "greater_than": op_greater_than,
    "greater_than_or_equal": op_greater_than_or_equal,
    "less_than": op_less_than,
    "less_than_or_equal": op_less_than_or_equal,
    "in": op_in,
    "not_in": op_not_in,
    "exists": op_exists,
    "contains": op_contains,
}


def evaluate_operator(operator: str, actual: Any, expected: Any) -> bool:
    """
    Safely dispatch an operator function.
    Raises ValueError on unsupported operators or invalid operands.
    """
    op_fn = OPERATORS.get(operator)
    if op_fn is None:
        supported = ", ".join(sorted(OPERATORS.keys()))
        raise ValueError(f"Unsupported eligibility operator '{operator}'. Supported operators: {supported}")
    return op_fn(actual, expected)
