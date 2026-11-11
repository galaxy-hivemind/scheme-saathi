"""
Deterministic eligibility rule operators and type-safe evaluation.
Pure Python implementation with no eval, exec, or external expression engines.
Includes strict boolean validation and safe type coercion.
"""
from typing import Any, Callable, Dict, List
from decimal import Decimal, InvalidOperation
from datetime import date, datetime


def parse_strict_bool(val: Any) -> bool:
    """
    Parse a value strictly as a boolean.
    Accepts:
      - Genuine Python booleans (True, False).
      - Strict string representations: 'true', '1', 'yes' (case-insensitive, trimmed) -> True
      - Strict string representations: 'false', '0', 'no' (case-insensitive, trimmed) -> False
    Rejects:
      - All other strings, numbers, collections, None with a controlled ValueError.
      - Arbitrary integers (e.g. 2, -1, 0, 1 as int/float/Decimal) are strictly rejected
        because numeric types must not be implicitly converted to booleans.
    """
    if type(val) is bool:
        return val

    if isinstance(val, str):
        norm = val.strip().lower()
        if norm in ("true", "1", "yes"):
            return True
        if norm in ("false", "0", "no"):
            return False
        raise ValueError(
            f"Invalid boolean string value: '{val}'. "
            f"Allowed boolean strings: 'true', 'false', '1', '0', 'yes', 'no'."
        )

    raise ValueError(
        f"Cannot interpret value of type '{type(val).__name__}' as a boolean: {val!r}. "
        f"Only booleans and allowed string representations ('true'/'false', '1'/'0', 'yes'/'no') are accepted."
    )


def _to_decimal(val: Any) -> Decimal:
    """Safely convert numeric or string values to Decimal for precise comparison."""
    if type(val) is bool:
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
    """Compare equality with strict boolean semantics, string case-insensitivity, and numeric coercion."""
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False

    # Strict Boolean Comparison:
    # If either operand is a boolean, both must be evaluated strictly as booleans
    if type(actual) is bool or type(expected) is bool:
        b_actual = parse_strict_bool(actual)
        b_expected = parse_strict_bool(expected)
        return b_actual is b_expected

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
    """Compare inequality with the same strict comparison semantics."""
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
    """
    Check whether field exists / is non-null and non-empty.
    Treats None, empty strings, and whitespace-only strings as nonexistent.
    Expected argument must be a genuine boolean or explicitly supported boolean string.
    """
    expected_bool = parse_strict_bool(expected)
    if actual is None:
        actual_exists = False
    elif isinstance(actual, str) and not actual.strip():
        actual_exists = False
    else:
        actual_exists = True
    return actual_exists is expected_bool


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
