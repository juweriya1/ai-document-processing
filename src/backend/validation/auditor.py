from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping

from src.backend.utils.currency import InvalidCurrencyError, normalize_amount, parse

TOLERANCE = Decimal("0.01")

_MAGNITUDE_RATIOS: tuple[Decimal, ...] = (
    Decimal("10"),
    Decimal("100"),
    Decimal("0.1"),
    Decimal("0.01"),
)
_MAGNITUDE_TOLERANCE = Decimal("0.05")  # ±5% of the target ratio


@dataclass(frozen=True)
class AuditReport:
    ok: bool
    total: Decimal | None
    subtotal: Decimal | None
    tax: Decimal | None
    delta: Decimal | None
    reason: str | None


def _get(fields: Mapping[str, str | None], name: str) -> str | None:
    v = fields.get(name)
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    return v


class FinancialAuditor:
    """Decimal-based math auditor.

    Verifies subtotal + tax == total (within 0.01 tolerance). Resilient to
    Pakistani/Indian currency formats via utils.currency.parse.
    """

    def audit(self, fields: Mapping[str, str | None]) -> AuditReport:
        total_raw = _get(fields, "total_amount") or _get(fields, "total")
        subtotal_raw = _get(fields, "subtotal")
        tax_raw = _get(fields, "tax")

        try:
            total = parse(total_raw) if total_raw else None
        except InvalidCurrencyError:
            return AuditReport(
                ok=False,
                total=None,
                subtotal=normalize_amount(subtotal_raw),
                tax=normalize_amount(tax_raw),
                delta=None,
                reason="unreadable_total",
            )

        subtotal = normalize_amount(subtotal_raw)
        tax = normalize_amount(tax_raw)

        if total is None:
            return AuditReport(
                ok=False,
                total=None,
                subtotal=subtotal,
                tax=tax,
                delta=None,
                reason="missing_total",
            )

        if subtotal is None or tax is None:
            return AuditReport(
                ok=True,
                total=total,
                subtotal=subtotal,
                tax=tax,
                delta=None,
                reason="partial_data",
            )

        computed = subtotal + tax
        delta = computed - total

        if abs(delta) <= TOLERANCE:
            return AuditReport(
                ok=True,
                total=total,
                subtotal=subtotal,
                tax=tax,
                delta=delta,
                reason=None,
            )
        return AuditReport(
            ok=False,
            total=total,
            subtotal=subtotal,
            tax=tax,
            delta=delta,
            reason="math_mismatch",
        )


_RECONSTRUCTION_TOLERANCE = Decimal("0.01")  # ±1% for the plug-it-back-in check


def _near(ratio: Decimal, target: Decimal) -> bool:
    if target == 0:
        return False
    return abs(ratio - target) / target <= _MAGNITUDE_TOLERANCE


def _match_ratio(ratio: Decimal) -> Decimal | None:
    for target in _MAGNITUDE_RATIOS:
        if _near(ratio, target):
            return target
    return None


def _balanced(lhs: Decimal, rhs: Decimal) -> bool:
    """True if lhs ≈ rhs within _RECONSTRUCTION_TOLERANCE (strict, ±1%)."""
    if rhs == 0:
        return abs(lhs) <= _RECONSTRUCTION_TOLERANCE
    return abs(lhs - rhs) / abs(rhs) <= _RECONSTRUCTION_TOLERANCE


def _triangulate_slipped_field(
    subtotal: Decimal, tax: Decimal, total: Decimal
) -> tuple[str, Decimal] | None:
    """Identify which of (subtotal, tax, total) is the likely slipped field.

    Rather than just finding a ratio near a power of 10, we *reconstruct* the
    equation with each candidate ratio applied and verify the reconstructed
    equation balances within a strict 1% tolerance. This eliminates false
    diagnoses on multi-field OCR errors where a naive ratio match might
    coincidentally land within 5% of 10.0 but not actually explain the mismatch.

    Returns (field_name, ratio) of the first candidate whose reconstruction
    balances tightly, or None if no single-field slip explains the mismatch.
    """
    for ratio in _MAGNITUDE_RATIOS:
        # "subtotal was off by `ratio`" → true subtotal = reported * ratio
        if subtotal != 0:
            if _balanced(subtotal * ratio + tax, total):
                return ("subtotal", ratio)
        # "tax was off by `ratio`" → true tax = reported * ratio
        if tax != 0:
            if _balanced(subtotal + tax * ratio, total):
                return ("tax", ratio)
        # "total was off by `ratio`" → true total = reported / ratio
        if ratio != 0 and _balanced(subtotal + tax, total / ratio):
            return ("total", ratio)

    return None


def _direction(field: str, ratio: Decimal) -> str:
    """Human-readable direction label given which field slipped and by what ratio.

    For subtotal/tax: ratio>1 means reported is too small (we multiply by >1 to
    recover the true value). For total: ratio>1 means reported is too large (we
    divide by >1 to recover the true value). This asymmetry matters — the VLM
    needs to know whether to look for missing digits or extra ones.
    """
    if field in ("subtotal", "tax"):
        return "too small" if ratio > 1 else "too large"
    return "too large" if ratio > 1 else "too small"


def _sum_line_items(line_items: Iterable[Mapping[str, Any]]) -> Decimal:
    total = Decimal("0")
    for it in line_items:
        if not isinstance(it, Mapping):
            continue
        val = normalize_amount(it.get("total"))
        if val is not None:
            total += val
    return total


def detect_magnitude_slip(
    report: AuditReport,
    line_items: Iterable[Mapping[str, Any]] | None = None,
) -> str | None:
    """Detect the "Decimal Slip": a power-of-10 error in one of the audited fields.

    Uses three-way triangulation to identify which specific field (subtotal, tax,
    or total) is the likely culprit, rather than blindly blaming total. When the
    top-level triangulation fails, falls back to comparing the reported total
    against the sum of line items — useful when both subtotal and a line item
    are mis-extracted together.

    Returns a VLM-ready guidance sentence naming the suspected field and the
    magnitude factor, or None if no clean single-field slip can explain the
    mismatch. Pure function — safe to call from any node.
    """
    if report.ok or report.reason != "math_mismatch":
        return None
    if report.subtotal is None or report.tax is None or report.total is None:
        return None

    slipped = _triangulate_slipped_field(report.subtotal, report.tax, report.total)
    if slipped is not None:
        field, ratio = slipped
        direction = _direction(field, ratio)
        return (
            f"magnitude_error: likely decimal-point slip in {field} — reported "
            f"{field} appears {direction} by a factor of ~{ratio} relative to "
            f"the other two fields. Observed: subtotal={report.subtotal}, "
            f"tax={report.tax}, total={report.total}. Re-scan the {field} field "
            "digit by digit and verify decimal placement before returning a value."
        )

    if line_items:
        items_total = _sum_line_items(line_items)
        if items_total != 0:
            items_ratio = report.total / items_total
            r = _match_ratio(items_ratio)
            if r is not None:
                return (
                    f"magnitude_error: the reported total ({report.total}) is "
                    f"~{r}x the sum of line items ({items_total}). The "
                    f"subtotal+tax triangulation was inconclusive, so a line "
                    f"item may also be mis-extracted. Re-scan every line item's "
                    f"amount and the total field, verifying decimal placement."
                )

    return None
