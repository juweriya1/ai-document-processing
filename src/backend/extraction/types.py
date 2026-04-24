from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractionResult:
    fields: dict[str, str | None] = field(default_factory=dict)
    line_items: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    raw_text: str = ""
    tier: str = "unknown"


EXPECTED_FIELDS = ("invoice_number", "date", "vendor_name", "subtotal", "tax", "total_amount")


def is_empty(result: ExtractionResult) -> bool:
    if not result.fields:
        return True
    return all(
        v is None or (isinstance(v, str) and not v.strip())
        for v in result.fields.values()
    )


def completeness(result: ExtractionResult) -> float:
    filled = sum(
        1 for k in EXPECTED_FIELDS
        if result.fields.get(k) and str(result.fields[k]).strip()
    )
    return filled / len(EXPECTED_FIELDS)
