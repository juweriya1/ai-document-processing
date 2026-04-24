from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_PREFIX = re.compile(r"^(rs\.?|pkr|inr|usd|\$|€|£)\s*", re.IGNORECASE)
_SUFFIX = re.compile(r"(/-|\s*rs\.?|\s*pkr)$", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


class InvalidCurrencyError(ValueError):
    pass


def _strip_currency_markers(s: str) -> str:
    s = s.strip()
    prev = None
    while prev != s:
        prev = s
        s = _PREFIX.sub("", s)
        s = _SUFFIX.sub("", s)
        s = s.strip()
    s = _WHITESPACE.sub("", s)
    return s


def _resolve_grouping(raw: str) -> str:
    if "," not in raw:
        return raw

    if "." in raw:
        int_part, _, frac_part = raw.rpartition(".")
    else:
        int_part, frac_part = raw, ""

    if "," not in int_part:
        return raw

    groups = int_part.split(",")
    head = groups[0]
    tail = groups[1:]

    if not head or not all(g.isdigit() for g in tail) or not head.lstrip("-").isdigit():
        raise InvalidCurrencyError(f"Unparseable currency grouping: {raw!r}")

    if tail[-1] and len(tail[-1]) != 3:
        raise InvalidCurrencyError(f"Last group must be 3 digits: {raw!r}")

    for g in tail[:-1]:
        if len(g) not in (2, 3):
            raise InvalidCurrencyError(f"Invalid group length: {raw!r}")

    clean_int = head + "".join(tail)
    return clean_int + (f".{frac_part}" if frac_part else "")


def parse(value: str | int | float | Decimal | None) -> Decimal:
    """Parse a currency string to Decimal.

    Handles Pakistani/Indian lakh grouping ("Rs. 1,50,000/-"), US grouping
    ("$1,500,000.00"), and bare numerics. Raises InvalidCurrencyError on bad input.
    """
    if value is None:
        raise InvalidCurrencyError("Cannot parse None as currency")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    if not isinstance(value, str):
        raise InvalidCurrencyError(f"Unsupported type: {type(value).__name__}")

    stripped = _strip_currency_markers(value)
    if not stripped:
        raise InvalidCurrencyError(f"Empty currency value: {value!r}")

    resolved = _resolve_grouping(stripped)

    if not _NUMERIC.match(resolved):
        raise InvalidCurrencyError(f"Not a valid number: {value!r}")

    try:
        return Decimal(resolved)
    except InvalidOperation as e:
        raise InvalidCurrencyError(f"Decimal conversion failed for {value!r}") from e


def normalize_amount(value: str | int | float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return parse(value)
    except InvalidCurrencyError:
        return None
