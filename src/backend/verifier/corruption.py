"""Domain-informed synthetic corruption operators.

Each operator takes a clean ExtractedInvoice and returns a corrupted copy
plus a tag describing what was corrupted. The trainer uses these to
manufacture (positive, negative) labeled pairs without any human labels —
self-supervision via plausible failure modes.

The operators reflect actual OCR / layout-extraction failures observed in
this system (decimal slips, field swaps, character confusion). They are
*not* random noise. Each one mimics a specific real-world bug class so
the trained verifier learns to recognize structural implausibility, not
arbitrary perturbation.

All operators are pure: same input + RNG state → same output. The
`apply_random` entry point handles RNG plumbing.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from src.backend.agents.state import ExtractedInvoice, LineItem
from src.backend.utils.currency import normalize_amount


@dataclass(frozen=True)
class CorruptionResult:
    invoice: ExtractedInvoice
    operator: str
    field: str | None  # which field was actually mutated, if applicable


# OCR confusion pairs (each pair is bidirectional). Drawn from the
# top recurring confusions in the PaddleOCR error log.
_OCR_CONFUSIONS: tuple[tuple[str, str], ...] = (
    ("0", "O"),
    ("1", "l"),
    ("1", "I"),
    ("5", "S"),
    ("8", "B"),
    ("6", "G"),
    ("2", "Z"),
    ("rn", "m"),
)

_NUMERIC_FIELDS: tuple[str, ...] = ("subtotal", "tax", "total_amount")
_TEXT_FIELDS: tuple[str, ...] = ("vendor_name",)
_MAGNITUDE_FACTORS: tuple[Decimal, ...] = (
    Decimal("10"),
    Decimal("100"),
    Decimal("0.1"),
    Decimal("0.01"),
)


def _scale_decimal_string(raw: str, factor: Decimal) -> str | None:
    """Multiply a currency-marker-bearing string by `factor`, preserving sign."""
    parsed = normalize_amount(raw)
    if parsed is None:
        return None
    scaled = parsed * factor
    # Preserve a fractional zero when the original looked decimal-ish.
    if "." in raw or factor < 1:
        # Keep two decimal places — invoice convention.
        scaled = scaled.quantize(Decimal("0.01"))
    return str(scaled)


def decimal_slip(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Multiply or divide a numeric field by a power of 10."""
    candidates = [f for f in _NUMERIC_FIELDS if getattr(inv, f)]
    if not candidates:
        return None
    field = rng.choice(candidates)
    factor = rng.choice(_MAGNITUDE_FACTORS)
    raw = getattr(inv, field)
    new_value = _scale_decimal_string(raw, factor)
    if new_value is None or new_value == raw:
        return None
    out = inv.model_copy(update={field: new_value})
    return CorruptionResult(invoice=out, operator="decimal_slip", field=field)


def digit_drop(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Remove a random digit from a numeric field."""
    candidates = [f for f in _NUMERIC_FIELDS if getattr(inv, f)]
    if not candidates:
        return None
    field = rng.choice(candidates)
    raw = getattr(inv, field)
    digit_positions = [i for i, c in enumerate(raw) if c.isdigit()]
    if not digit_positions:
        return None
    pos = rng.choice(digit_positions)
    new_value = raw[:pos] + raw[pos + 1 :]
    if not new_value or new_value == raw:
        return None
    out = inv.model_copy(update={field: new_value})
    return CorruptionResult(invoice=out, operator="digit_drop", field=field)


def digit_insert(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Insert a digit at a random position inside a numeric field."""
    candidates = [f for f in _NUMERIC_FIELDS if getattr(inv, f)]
    if not candidates:
        return None
    field = rng.choice(candidates)
    raw = getattr(inv, field)
    digit_positions = [i for i, c in enumerate(raw) if c.isdigit()]
    if not digit_positions:
        return None
    pos = rng.choice(digit_positions)
    inserted = rng.choice("0123456789")
    new_value = raw[:pos] + inserted + raw[pos:]
    out = inv.model_copy(update={field: new_value})
    return CorruptionResult(invoice=out, operator="digit_insert", field=field)


def field_swap(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Swap two numeric fields' values (subtotal↔total, subtotal↔tax, etc.)."""
    populated = [f for f in _NUMERIC_FIELDS if getattr(inv, f)]
    if len(populated) < 2:
        return None
    a, b = rng.sample(populated, 2)
    val_a, val_b = getattr(inv, a), getattr(inv, b)
    if val_a == val_b:
        return None
    out = inv.model_copy(update={a: val_b, b: val_a})
    return CorruptionResult(invoice=out, operator="field_swap", field=f"{a},{b}")


def tax_sign_flip(inv: ExtractedInvoice, _rng: random.Random) -> CorruptionResult | None:
    """Negate the tax field. Reflects sign-parsing errors on credit-note layouts."""
    if not inv.tax:
        return None
    parsed = normalize_amount(inv.tax)
    if parsed is None or parsed == 0:
        return None
    new_value = str(-parsed)
    out = inv.model_copy(update={"tax": new_value})
    return CorruptionResult(invoice=out, operator="tax_sign_flip", field="tax")


def ocr_confusion(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Apply a confusion-matrix substitution to a text or numeric field."""
    populated = [
        f for f in (*_NUMERIC_FIELDS, *_TEXT_FIELDS, "invoice_number") if getattr(inv, f)
    ]
    if not populated:
        return None
    field = rng.choice(populated)
    raw = getattr(inv, field)
    pairs = list(_OCR_CONFUSIONS)
    rng.shuffle(pairs)
    for a, b in pairs:
        if a in raw:
            new_value = raw.replace(a, b, 1)
            if new_value != raw:
                out = inv.model_copy(update={field: new_value})
                return CorruptionResult(invoice=out, operator="ocr_confusion", field=field)
        if b in raw:
            new_value = raw.replace(b, a, 1)
            if new_value != raw:
                out = inv.model_copy(update={field: new_value})
                return CorruptionResult(invoice=out, operator="ocr_confusion", field=field)
    return None


_DATE_RE = re.compile(r"^(\d{1,2})([/\-.])(\d{1,2})([/\-.])(\d{2,4})$")


def date_format_swap(inv: ExtractedInvoice, _rng: random.Random) -> CorruptionResult | None:
    """Swap MM/DD ↔ DD/MM. Only meaningful when both halves ≤ 12 — but the
    verifier should learn that even ambiguous dates skewed toward implausible
    interpretations are suspicious in context.
    """
    if not inv.date:
        return None
    m = _DATE_RE.match(inv.date.strip())
    if not m:
        return None
    a, sep1, b, sep2, year = m.groups()
    new_value = f"{b}{sep1}{a}{sep2}{year}"
    if new_value == inv.date.strip():
        return None
    out = inv.model_copy(update={"date": new_value})
    return CorruptionResult(invoice=out, operator="date_format_swap", field="date")


def vendor_perturb(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Apply 1-3 character edits to vendor name."""
    if not inv.vendor_name or len(inv.vendor_name) < 3:
        return None
    raw = inv.vendor_name
    edits = rng.randint(1, min(3, max(1, len(raw) // 4)))
    chars = list(raw)
    for _ in range(edits):
        op = rng.choice(("substitute", "delete", "insert"))
        if not chars:
            break
        pos = rng.randrange(len(chars))
        if op == "substitute":
            chars[pos] = rng.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
        elif op == "delete":
            chars.pop(pos)
        else:  # insert
            chars.insert(pos, rng.choice("abcdefghijklmnopqrstuvwxyz"))
    new_value = "".join(chars)
    if new_value == raw or not new_value:
        return None
    out = inv.model_copy(update={"vendor_name": new_value})
    return CorruptionResult(invoice=out, operator="vendor_perturb", field="vendor_name")


def line_item_drop(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Drop a random line item. Mimics detection misses."""
    if len(inv.line_items) < 2:
        return None
    idx = rng.randrange(len(inv.line_items))
    items = [li for i, li in enumerate(inv.line_items) if i != idx]
    out = inv.model_copy(update={"line_items": items})
    return CorruptionResult(invoice=out, operator="line_item_drop", field=f"line_items[{idx}]")


def line_item_duplicate(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Duplicate a random line item with slight modification. Mimics segmentation errors."""
    if not inv.line_items:
        return None
    idx = rng.randrange(len(inv.line_items))
    src = inv.line_items[idx]
    dup = LineItem(
        description=src.description,
        quantity=src.quantity,
        unit_price=src.unit_price,
        total=src.total,
    )
    items = list(inv.line_items)
    items.insert(idx + 1, dup)
    out = inv.model_copy(update={"line_items": items})
    return CorruptionResult(
        invoice=out, operator="line_item_duplicate", field=f"line_items[{idx}]"
    )


def quantity_price_skew(
    inv: ExtractedInvoice, rng: random.Random
) -> CorruptionResult | None:
    """Modify a line-item quantity OR unit_price so qty × price ≠ stated total.

    The corruption is to ONE of the three numeric line-item fields, leaving
    the other two intact — so the inconsistency is detectable.
    """
    candidates: list[int] = []
    for i, li in enumerate(inv.line_items):
        if (li.quantity or li.unit_price) and li.total:
            candidates.append(i)
    if not candidates:
        return None
    idx = rng.choice(candidates)
    li = inv.line_items[idx]
    target = rng.choice(("quantity", "unit_price"))
    raw = getattr(li, target)
    if not raw:
        target = "quantity" if target == "unit_price" else "unit_price"
        raw = getattr(li, target)
    if not raw:
        return None
    parsed = normalize_amount(raw)
    if parsed is None or parsed == 0:
        return None
    factor = rng.choice([Decimal("2"), Decimal("0.5"), Decimal("3")])
    new_raw = str((parsed * factor).quantize(Decimal("0.01")))
    new_li = li.model_copy(update={target: new_raw})
    items = list(inv.line_items)
    items[idx] = new_li
    out = inv.model_copy(update={"line_items": items})
    return CorruptionResult(
        invoice=out, operator="quantity_price_skew", field=f"line_items[{idx}].{target}"
    )


def currency_mismatch(inv: ExtractedInvoice, rng: random.Random) -> CorruptionResult | None:
    """Inject a foreign currency marker on one numeric field so currency is mixed."""
    populated = [f for f in _NUMERIC_FIELDS if getattr(inv, f)]
    if not populated:
        return None
    field = rng.choice(populated)
    raw = getattr(inv, field)
    parsed = normalize_amount(raw)
    if parsed is None:
        return None
    foreign = rng.choice(("$", "€", "£"))
    if foreign in raw:
        return None
    new_value = f"{foreign}{parsed}"
    out = inv.model_copy(update={field: new_value})
    return CorruptionResult(invoice=out, operator="currency_mismatch", field=field)


# Registry. Order is irrelevant — apply_random samples uniformly.
ALL_OPERATORS: tuple[Callable[[ExtractedInvoice, random.Random], CorruptionResult | None], ...] = (
    decimal_slip,
    digit_drop,
    digit_insert,
    field_swap,
    tax_sign_flip,
    ocr_confusion,
    date_format_swap,
    vendor_perturb,
    line_item_drop,
    line_item_duplicate,
    quantity_price_skew,
    currency_mismatch,
)


def apply_random(
    inv: ExtractedInvoice,
    rng: random.Random,
    max_attempts: int = 8,
) -> CorruptionResult | None:
    """Pick a random operator and apply it. Retries up to `max_attempts`
    operators if the first ones return None (e.g. a swap on a single-field
    invoice). Returns None only if every sampled operator fails.
    """
    operators = list(ALL_OPERATORS)
    rng.shuffle(operators)
    for op in operators[:max_attempts]:
        result = op(inv, rng)
        if result is not None:
            return result
    return None
