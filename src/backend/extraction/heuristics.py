from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from src.backend.utils.currency import InvalidCurrencyError, parse as parse_amount

_AMOUNT_PREFIX = r"(?:rs\.?|pkr|\$|€|£)"
_AMOUNT_SUFFIX = r"(?:\s*/-)?"

_VALUE_ONLY_PATTERNS = [
    re.compile(
        rf"^\s*{_AMOUNT_PREFIX}\s*([\d,]+(?:\.\d{{1,2}})?){_AMOUNT_SUFFIX}\s*$",
        re.IGNORECASE,
    ),
    re.compile(rf"^\s*([\d,]+\.\d{{1,2}}){_AMOUNT_SUFFIX}\s*$"),
    re.compile(r"^\s*([\d,]+)\s*/-\s*$"),
]

_EMBEDDED_AMOUNT = re.compile(
    rf"{_AMOUNT_PREFIX}\s*([\d,]+(?:\.\d{{1,2}})?){_AMOUNT_SUFFIX}"
    rf"|([\d,]+\.\d{{1,2}}){_AMOUNT_SUFFIX}",
    re.IGNORECASE,
)

_DEC_AMT = rf"{_AMOUNT_PREFIX}?\s*([\d,]+\.\d{{1,2}}{_AMOUNT_SUFFIX})"
_PK_AMT = rf"(?:rs\.?|pkr)\s*([\d,]+(?:\.\d{{1,2}})?{_AMOUNT_SUFFIX})"

_REGEX_PATTERNS = {
    "invoice_number": [
        re.compile(r"(?i)invoice\s*(?:no\.?|number|#)[:\s]*([A-Z0-9\-/]+)"),
        re.compile(r"\b(INV[-/][A-Z0-9\-/]+)\b"),
    ],
    "date": [
        re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
        re.compile(r"\b(\d{2}/\d{2}/\d{4})\b"),
        re.compile(r"\b(\d{2}-\d{2}-\d{4})\b"),
        re.compile(
            r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
            re.IGNORECASE,
        ),
    ],
    "total_amount": [
        re.compile(r"(?i)(?:grand|invoice)\s+total[^\n\r]{0,60}?" + _DEC_AMT),
        re.compile(r"(?i)\btotal\s*(?:amount|due|payable)?[^\n\r]{0,60}?" + _DEC_AMT),
        re.compile(r"(?i)amount\s+(?:paid|due)[^\n\r]{0,60}?" + _DEC_AMT),
        re.compile(r"(?i)total[^\n\r]{0,60}?" + _PK_AMT),
    ],
    "subtotal": [
        re.compile(r"(?i)sub[-\s]?total[^\n\r]{0,60}?" + _DEC_AMT),
        re.compile(r"(?i)sub[-\s]?total[^\n\r]{0,60}?" + _PK_AMT),
    ],
    "tax": [
        re.compile(r"(?i)(?:tax|vat|gst|sales\s*tax)[^\n\r]{0,60}?" + _DEC_AMT),
        re.compile(r"(?i)(?:tax|vat|gst|sales\s*tax)[^\n\r]{0,60}?" + _PK_AMT),
    ],
    "vendor_name": [
        re.compile(r"(?im)^\s*(?:vendor|supplier|from)[:\s]+(.+?)$"),
    ],
}


_LABEL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "total_amount": [
        re.compile(r"(?i)^\s*grand\s+total\s*:?\s*$"),
        re.compile(r"(?i)^\s*invoice\s+total\s*:?\s*$"),
        re.compile(r"(?i)^\s*total\s+due\s*:?\s*$"),
        re.compile(r"(?i)^\s*total\s+payable\s*:?\s*$"),
        re.compile(r"(?i)^\s*total\s+amount\s*:?\s*$"),
        re.compile(r"(?i)^\s*amount\s+due\s*:?\s*$"),
        re.compile(r"(?i)^\s*amount\s+paid\s*:?\s*$"),
        re.compile(r"(?i)^\s*balance\s+due\s*:?\s*$"),
        re.compile(r"(?i)^\s*total\s*:?\s*$"),
    ],
    "subtotal": [
        re.compile(r"(?i)^\s*sub[-\s]?total\s*:?\s*$"),
    ],
    "tax": [
        re.compile(r"(?i)^\s*(?:sales\s*tax|vat|gst|tax)\s*:?\s*$"),
    ],
    "invoice_number": [
        re.compile(r"(?i)^\s*invoice\s*(?:no\.?|number|#)\s*:?\s*$"),
        re.compile(r"(?i)^\s*(?:invoice|inv)\s*#\s*$"),
    ],
    "date": [
        re.compile(r"(?i)^\s*(?:invoice\s+)?date\s*:?\s*$"),
        re.compile(r"(?i)^\s*due\s+date\s*:?\s*$"),
    ],
    "vendor_name": [
        re.compile(r"(?i)^\s*(?:vendor|supplier|from|bill\s+from)\s*:?\s*$"),
    ],
}

_TOTAL_FIELDS = ("total_amount", "subtotal", "tax")
_TRIANGULATE_TOLERANCE = Decimal("0.02")


@dataclass
class OCRBlock:
    text: str
    score: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def height(self) -> float:
        return max(self.y2 - self.y1, 1.0)

    @property
    def width(self) -> float:
        return max(self.x2 - self.x1, 1.0)


def _normalize_amount_match(s: str) -> str:
    return s.strip().rstrip(",").strip()


def _classify_label(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    for field, patterns in _LABEL_PATTERNS.items():
        for pat in patterns:
            if pat.match(stripped):
                return field
    return None


def _is_amount_block(text: str) -> str | None:
    stripped = text.strip()
    for pat in _VALUE_ONLY_PATTERNS:
        m = pat.match(stripped)
        if m:
            candidate = m.group(1).strip().rstrip(",")
            if any(ch.isdigit() for ch in candidate):
                return candidate
    return None


def _find_value_for_label(label: OCRBlock, blocks: list[OCRBlock]) -> OCRBlock | None:
    row_tol = label.height * 0.9
    candidates_right: list[tuple[float, OCRBlock]] = []
    candidates_below: list[tuple[float, OCRBlock]] = []

    for b in blocks:
        if b is label:
            continue
        if _is_amount_block(b.text) is None:
            continue
        dy = b.cy - label.cy
        same_row = abs(dy) <= row_tol
        if same_row and b.x1 >= label.x2 - label.width * 0.25:
            candidates_right.append((b.x1 - label.x2, b))
            continue
        if b.y1 >= label.y2 - row_tol * 0.25:
            col_dist = abs(b.cx - label.cx)
            if col_dist <= max(label.width * 3, label.height * 6):
                candidates_below.append((b.y1 - label.y2 + col_dist * 0.25, b))

    if candidates_right:
        candidates_right.sort(key=lambda t: t[0])
        return candidates_right[0][1]
    if candidates_below:
        candidates_below.sort(key=lambda t: t[0])
        return candidates_below[0][1]
    return None


def _find_text_value_for_label(label: OCRBlock, blocks: list[OCRBlock]) -> OCRBlock | None:
    row_tol = label.height * 0.9
    right_same_row: list[tuple[float, OCRBlock]] = []
    below_same_col: list[tuple[float, OCRBlock]] = []

    for b in blocks:
        if b is label:
            continue
        stripped = b.text.strip()
        if not stripped:
            continue
        if _classify_label(stripped):
            continue
        dy = b.cy - label.cy
        same_row = abs(dy) <= row_tol
        if same_row and b.x1 >= label.x2 - label.width * 0.25:
            right_same_row.append((b.x1 - label.x2, b))
            continue
        if b.y1 >= label.y2 - row_tol * 0.25:
            col_dist = abs(b.cx - label.cx)
            if col_dist <= max(label.width * 2, label.height * 4):
                below_same_col.append((b.y1 - label.y2 + col_dist * 0.25, b))

    if right_same_row:
        right_same_row.sort(key=lambda t: t[0])
        return right_same_row[0][1]
    if below_same_col:
        below_same_col.sort(key=lambda t: t[0])
        return below_same_col[0][1]
    return None


def _collect_amount_values(blocks: Iterable[OCRBlock]) -> list[tuple[Decimal, str, OCRBlock]]:
    """Return (decimal_value, display_text, block) for every amount-looking block."""
    out: list[tuple[Decimal, str, OCRBlock]] = []
    for b in blocks:
        token = _is_amount_block(b.text)
        if token is None:
            continue
        try:
            value = parse_amount(token)
        except InvalidCurrencyError:
            continue
        if value <= 0:
            continue
        out.append((value, token, b))
    return out


def _triangulate_totals(
    candidates: list[tuple[Decimal, str, OCRBlock]],
    existing: dict[str, str | None],
) -> dict[str, str | None]:
    """Find a (subtotal, tax, total) triple where subtotal + tax == total.

    Picks the triple with the largest total (grand total typically dominates).
    Does not overwrite existing values.
    """
    if len(candidates) < 3:
        return {}

    best: tuple[Decimal, str, str, str] | None = None  # (total_val, sub, tax, total)

    by_value: dict[Decimal, list[tuple[str, OCRBlock]]] = {}
    for value, token, block in candidates:
        by_value.setdefault(value, []).append((token, block))

    values = sorted(by_value.keys(), reverse=True)

    for total_val in values:
        for sub_val in values:
            if sub_val >= total_val:
                continue
            needed = total_val - sub_val
            if needed <= 0:
                continue
            for tax_val in by_value:
                if abs(tax_val - needed) <= _TRIANGULATE_TOLERANCE:
                    if tax_val >= total_val:
                        continue
                    sub_token = by_value[sub_val][0][0]
                    tax_token = by_value[tax_val][0][0]
                    total_token = by_value[total_val][0][0]
                    if best is None or total_val > best[0]:
                        best = (total_val, sub_token, tax_token, total_token)
                    break

    if best is None:
        return {}

    _, sub_token, tax_token, total_token = best
    out: dict[str, str | None] = {}
    if not existing.get("total_amount"):
        out["total_amount"] = total_token
    if not existing.get("subtotal"):
        out["subtotal"] = sub_token
    if not existing.get("tax"):
        out["tax"] = tax_token
    return out


def apply_spatial_heuristics(blocks: Iterable[OCRBlock]) -> dict[str, str | None]:
    """Pair labels with adjacent values using layout geometry."""
    blocks = [b for b in blocks if b.text and b.text.strip()]
    if not blocks:
        return {}

    out: dict[str, str | None] = {}
    used_value_ids: set[int] = set()

    for block in blocks:
        label_field = _classify_label(block.text)
        if label_field is None:
            continue
        if out.get(label_field):
            continue

        if label_field in _TOTAL_FIELDS:
            value = _find_value_for_label(block, blocks)
        else:
            value = _find_text_value_for_label(block, blocks)

        if value is None or id(value) in used_value_ids:
            continue

        if label_field in _TOTAL_FIELDS:
            amount = _is_amount_block(value.text)
            if amount is None:
                continue
            out[label_field] = amount
        else:
            out[label_field] = value.text.strip()
        used_value_ids.add(id(value))

    return out


def apply_heuristics(
    text: str,
    existing: dict[str, str | None] | None = None,
    blocks: Iterable[OCRBlock] | None = None,
) -> dict[str, str | None]:
    """Extract fields. Order of precedence:
      1. values passed in `existing` (kept untouched)
      2. layout-aware pairing from `blocks`
      3. regex on raw text
      4. financial triangulation over all detected amount values
    """
    out: dict[str, str | None] = {k: v for k, v in (existing or {}).items() if v}
    block_list = [b for b in (blocks or []) if b.text and b.text.strip()]

    if block_list:
        spatial = apply_spatial_heuristics(block_list)
        for k, v in spatial.items():
            if v and not out.get(k):
                out[k] = v

    if text:
        for name, patterns in _REGEX_PATTERNS.items():
            if out.get(name):
                continue
            for pat in patterns:
                m = pat.search(text)
                if not m:
                    continue
                value = _normalize_amount_match(m.group(1))
                if value:
                    out[name] = value
                    break

    missing_totals = [f for f in _TOTAL_FIELDS if not out.get(f)]
    if missing_totals and block_list:
        candidates = _collect_amount_values(block_list)
        triangulated = _triangulate_totals(candidates, out)
        for k, v in triangulated.items():
            if v and not out.get(k):
                out[k] = v

    return out
