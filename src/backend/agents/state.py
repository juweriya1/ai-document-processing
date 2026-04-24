from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    total: str | None = None


class ExtractedInvoice(BaseModel):
    """Pydantic mirror of the BAML `InvoiceExtraction` class with line_items.

    All numeric fields stay as strings here — the currency parser in
    `utils.currency` handles coercion to Decimal at audit time, preserving
    region-specific markers (Rs., /-, lakh grouping) exactly as extracted.
    """

    invoice_number: str | None = None
    date: str | None = None
    vendor_name: str | None = None
    subtotal: str | None = None
    tax: str | None = None
    total_amount: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)


class AgentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document_id: str
    file_path: str
    pages: list[Any] | None = None
    extracted_data: ExtractedInvoice | None = None
    audit_log: list[dict[str, Any]] = Field(default_factory=list)
    attempts: int = 0
    is_valid: bool = False
    tier: Literal["local", "vlm", "hitl"] = "local"
    reason: str | None = None
    # OCR-level confidence of the most recent extraction (0.0–1.0). Populated
    # by ocr_node / reconciler_node. auditor_node escalates to Tier-2 when this
    # drops below LOCAL_CONFIDENCE_THRESHOLD even if the math happens to balance.
    ocr_confidence: float | None = None
    # Set by auditor_node on failure; consumed verbatim by reconciler_node to
    # build the `error_context` argument of the BAML `ReconcileInvoice` call.
    reconciliation_guidance: str | None = None
