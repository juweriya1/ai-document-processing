"""Deterministic feature extraction for the plausibility verifier.

The verifier scores the *extracted representation* (not the raw image) so it
runs in <1ms at inference and forces the model to learn structural / numeric
plausibility. Produces a fixed-order vector of ~40 numeric features.

Feature groups (mirrors the plan):
  1. Arithmetic residuals — sum/total/tax/line-item invariants
  2. Magnitude features — log scales, ratios
  3. Structural features — line-item count, presence flags
  4. Text features — vendor name shape, date validity, invoice-number regex
  5. Confidence features — OCR aggregate (per-field is deferred; see plan)
  6. Cross-field consistency — currency consistency, date sanity

NaN handling: missing-value features become 0.0 with a paired presence flag,
so the model can learn "field is absent" as a signal without conflating it
with "field equals zero."
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from src.backend.agents.state import ExtractedInvoice, LineItem
from src.backend.utils.currency import normalize_amount


# Stable feature ordering. Adding a feature here = retrain. The
# `feature_schema_hash` saved in the model artifact catches mismatches at
# inference time so the predictor refuses to serve a stale model against a
# changed feature set.
FEATURE_NAMES: tuple[str, ...] = (
    # Group 1: arithmetic residuals
    "math_residual_relative",       # (subtotal + tax - total) / max(|total|, 1)
    "math_residual_absolute",       # |subtotal + tax - total|
    "line_items_sum_residual",      # (Σ line_items - subtotal) / max(|subtotal|, 1)
    "line_items_arithmetic_failrate",  # fraction of line items where qty*price != total
    "line_items_arithmetic_max_dev",   # max relative deviation across all line items
    # Group 2: magnitude
    "log_total",                    # log10(max(|total|, 1))
    "log_subtotal",
    "log_tax",
    "ratio_max_lineitem_to_total",  # max(line_item_total) / total
    "ratio_min_lineitem_to_total",  # min(positive line_item_total) / total
    "tax_to_subtotal_ratio",        # tax / subtotal — typical 0..0.3
    "decimal_places_total",
    "decimal_places_subtotal",
    "decimal_places_tax",
    # Group 3: structural
    "n_line_items",
    "has_invoice_number",
    "has_date",
    "has_vendor_name",
    "has_subtotal",
    "has_tax",
    "has_total",
    "all_line_items_have_total",
    "all_line_items_have_quantity_and_price",
    # Group 4: text
    "vendor_name_length",
    "vendor_name_has_digits",
    "vendor_name_uppercase_ratio",
    "vendor_name_has_punct",
    "invoice_number_length",
    "invoice_number_alnum_ratio",
    "date_parses",
    "date_within_5_years",
    # Group 5: confidence
    "ocr_confidence",
    "ocr_confidence_below_85",
    # Group 6: cross-field consistency
    "currency_marker_consistent",
    "currency_marker_count_distinct",
    "negative_amount_present",
    "all_amounts_round",            # all amounts end in .00 — common forgery / parser tell
    "tax_sign_negative",
)

N_FEATURES = len(FEATURE_NAMES)


@dataclass(frozen=True)
class FeatureVector:
    values: tuple[float, ...]
    schema_hash: str

    def to_dict(self) -> dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.values))


def _decimal_or_zero(raw: str | None) -> Decimal:
    parsed = normalize_amount(raw)
    return parsed if parsed is not None else Decimal(0)


def _decimal_or_none(raw: str | None) -> Decimal | None:
    return normalize_amount(raw)


def _safe_log10(x: Decimal) -> float:
    val = abs(float(x))
    if val < 1e-9:
        return 0.0
    return math.log10(val)


def _decimal_places(raw: str | None) -> int:
    if not raw:
        return 0
    parsed = _decimal_or_none(raw)
    if parsed is None:
        return 0
    s = str(parsed)
    if "." not in s:
        return 0
    return len(s.split(".", 1)[1])


_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
    "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y",
    "%B %d, %Y",
)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


_CURRENCY_MARKER_RE = re.compile(r"(rs\.?|pkr|inr|usd|\$|€|£)", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s]")


def _currency_markers(raws: Iterable[str | None]) -> set[str]:
    seen: set[str] = set()
    for r in raws:
        if not r:
            continue
        for m in _CURRENCY_MARKER_RE.findall(r):
            seen.add(m.lower().rstrip("."))
    return seen


def _line_item_arithmetic_stats(items: Iterable[LineItem]) -> tuple[float, float]:
    """Return (failrate, max_dev) for line-item qty × price ≈ total checks.

    failrate: fraction of items where the per-line invariant is violated.
    max_dev: the maximum relative deviation across all checked items.
    Items that lack at least two of the three numeric fields are skipped.
    """
    fail = 0
    checked = 0
    max_dev = 0.0
    for li in items:
        qty = _decimal_or_none(li.quantity)
        price = _decimal_or_none(li.unit_price)
        total = _decimal_or_none(li.total)
        if qty is None or price is None or total is None:
            continue
        expected = qty * price
        if total == 0 and expected == 0:
            checked += 1
            continue
        if abs(total) < Decimal("0.01"):
            checked += 1
            if abs(expected) >= Decimal("0.01"):
                fail += 1
                max_dev = max(max_dev, float(abs(expected)))
            continue
        dev = abs(float(expected - total) / float(total))
        max_dev = max(max_dev, dev)
        if dev > 0.01:
            fail += 1
        checked += 1
    if checked == 0:
        return 0.0, 0.0
    return fail / checked, max_dev


def _has_round_amounts(values: Iterable[Decimal | None]) -> bool:
    """All non-None decimal values are integer-valued (e.g. .00). Empty → False."""
    seen = False
    for v in values:
        if v is None:
            continue
        seen = True
        if v != v.to_integral_value():
            return False
    return seen


# Schema hash — bumped automatically by hashing FEATURE_NAMES so any
# inadvertent reorder/rename invalidates a cached model.
def _compute_schema_hash() -> str:
    import hashlib

    return hashlib.sha256("|".join(FEATURE_NAMES).encode()).hexdigest()[:16]


SCHEMA_HASH = _compute_schema_hash()


def extract_features(
    invoice: ExtractedInvoice,
    ocr_confidence: float | None = None,
    today: date | None = None,
) -> FeatureVector:
    """Compute the fixed-order feature vector for one extraction.

    Args:
        invoice: extracted fields + line items
        ocr_confidence: aggregate OCR confidence (0.0–1.0); None → 0.0
        today: reference date for "within 5 years" check; defaults to now
               (parameterized for deterministic tests)
    """
    today = today or datetime.now(timezone.utc).date()

    total = _decimal_or_none(invoice.total_amount)
    subtotal = _decimal_or_none(invoice.subtotal)
    tax = _decimal_or_none(invoice.tax)

    # Group 1 — arithmetic residuals
    if total is None or subtotal is None or tax is None:
        math_residual_rel = 0.0
        math_residual_abs = 0.0
    else:
        residual = subtotal + tax - total
        math_residual_abs = float(abs(residual))
        denom = max(abs(float(total)), 1.0)
        math_residual_rel = float(abs(residual)) / denom

    line_items_sum = sum(
        (_decimal_or_zero(li.total) for li in invoice.line_items), Decimal(0)
    )
    if subtotal is None or subtotal == 0:
        line_items_sum_residual = 0.0
    else:
        line_items_sum_residual = float(abs(line_items_sum - subtotal)) / max(
            abs(float(subtotal)), 1.0
        )

    failrate, max_dev = _line_item_arithmetic_stats(invoice.line_items)

    # Group 2 — magnitude
    log_total = _safe_log10(total) if total else 0.0
    log_subtotal = _safe_log10(subtotal) if subtotal else 0.0
    log_tax = _safe_log10(tax) if tax else 0.0

    item_totals = [
        _decimal_or_zero(li.total) for li in invoice.line_items if li.total
    ]
    item_total_floats = [abs(float(v)) for v in item_totals if v != 0]
    if item_total_floats and total and abs(float(total)) > 1e-9:
        denom = abs(float(total))
        ratio_max = max(item_total_floats) / denom
        ratio_min = min(item_total_floats) / denom
    else:
        ratio_max = 0.0
        ratio_min = 0.0

    if subtotal and abs(float(subtotal)) > 1e-9 and tax is not None:
        tax_to_subtotal = float(tax) / float(subtotal)
    else:
        tax_to_subtotal = 0.0

    dp_total = _decimal_places(invoice.total_amount)
    dp_subtotal = _decimal_places(invoice.subtotal)
    dp_tax = _decimal_places(invoice.tax)

    # Group 3 — structural
    n_items = len(invoice.line_items)
    has_inv_no = 1.0 if invoice.invoice_number else 0.0
    has_date = 1.0 if invoice.date else 0.0
    has_vendor = 1.0 if invoice.vendor_name else 0.0
    has_subtotal = 1.0 if invoice.subtotal else 0.0
    has_tax = 1.0 if invoice.tax else 0.0
    has_total = 1.0 if invoice.total_amount else 0.0
    all_have_total = 1.0 if (
        invoice.line_items and all(li.total for li in invoice.line_items)
    ) else 0.0
    all_have_qty_price = 1.0 if (
        invoice.line_items
        and all(li.quantity and li.unit_price for li in invoice.line_items)
    ) else 0.0

    # Group 4 — text
    vendor = invoice.vendor_name or ""
    vendor_len = float(len(vendor))
    vendor_has_digits = 1.0 if any(c.isdigit() for c in vendor) else 0.0
    if vendor:
        upper_count = sum(1 for c in vendor if c.isupper())
        vendor_upper_ratio = upper_count / max(len(vendor), 1)
    else:
        vendor_upper_ratio = 0.0
    vendor_has_punct = 1.0 if _PUNCT_RE.search(vendor) else 0.0

    inv_no = invoice.invoice_number or ""
    inv_no_len = float(len(inv_no))
    if inv_no:
        alnum_count = sum(1 for c in inv_no if c.isalnum())
        inv_no_alnum_ratio = alnum_count / max(len(inv_no), 1)
    else:
        inv_no_alnum_ratio = 0.0

    parsed_date = _parse_date(invoice.date)
    date_parses_f = 1.0 if parsed_date else 0.0
    if parsed_date:
        diff_days = abs((today - parsed_date).days)
        date_within_5y = 1.0 if diff_days <= 5 * 366 else 0.0
    else:
        date_within_5y = 0.0

    # Group 5 — confidence
    ocr_conf = float(ocr_confidence) if ocr_confidence is not None else 0.0
    ocr_below_85 = 1.0 if ocr_conf < 0.85 else 0.0

    # Group 6 — cross-field
    raws = [
        invoice.subtotal, invoice.tax, invoice.total_amount,
        *(li.unit_price for li in invoice.line_items),
        *(li.total for li in invoice.line_items),
    ]
    markers = _currency_markers(raws)
    marker_count = float(len(markers))
    marker_consistent = 1.0 if len(markers) <= 1 else 0.0

    any_negative = any(
        (v is not None and v < 0)
        for v in (subtotal, tax, total)
    ) or any(
        (_decimal_or_none(li.total) or Decimal(0)) < 0
        for li in invoice.line_items
    )
    negative_amount = 1.0 if any_negative else 0.0

    round_amounts = 1.0 if _has_round_amounts((subtotal, tax, total)) else 0.0
    tax_neg = 1.0 if (tax is not None and tax < 0) else 0.0

    values = (
        # Group 1
        math_residual_rel,
        math_residual_abs,
        line_items_sum_residual,
        failrate,
        max_dev,
        # Group 2
        log_total,
        log_subtotal,
        log_tax,
        ratio_max,
        ratio_min,
        tax_to_subtotal,
        float(dp_total),
        float(dp_subtotal),
        float(dp_tax),
        # Group 3
        float(n_items),
        has_inv_no,
        has_date,
        has_vendor,
        has_subtotal,
        has_tax,
        has_total,
        all_have_total,
        all_have_qty_price,
        # Group 4
        vendor_len,
        vendor_has_digits,
        vendor_upper_ratio,
        vendor_has_punct,
        inv_no_len,
        inv_no_alnum_ratio,
        date_parses_f,
        date_within_5y,
        # Group 5
        ocr_conf,
        ocr_below_85,
        # Group 6
        marker_consistent,
        marker_count,
        negative_amount,
        round_amounts,
        tax_neg,
    )
    assert len(values) == N_FEATURES, (
        f"feature vector length mismatch: got {len(values)}, expected {N_FEATURES}"
    )
    return FeatureVector(values=values, schema_hash=SCHEMA_HASH)
