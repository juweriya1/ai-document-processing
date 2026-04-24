"""Force the reconciliation loop to fire against real Gemini.

Uses the real PaddleOCR output but injects a 10x decimal slip in `total_amount`
before the auditor sees it. The auditor will flag a magnitude_error, and
reconciler_node will call the real BAML ReconcileInvoice against the real
Gemini 2.5 Flash endpoint. Observes whether Gemini corrects the slip.

This is the test the stubbed graph-BDD tests cannot run: it proves the full
chain — BAML client generation, the Python-to-Gemini wire format, the prompt
rendering, and the response coercion — actually works end to end.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/smoke_agentic_vlm.py [document_id]
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

from src.backend.agents import nodes
from src.backend.agents.graph import build_graph
from src.backend.agents.state import AgentState, ExtractedInvoice
from src.backend.db.database import SessionLocal
from src.backend.db.models import Document
from src.backend.extraction.local_extractor import LocalExtractor
from src.backend.extraction.types import ExtractionResult


class _SlipInjector:
    """Wraps the real LocalExtractor and inflates total_amount by 10x
    (the classic "decimal slip") so the auditor flags a magnitude error."""

    def __init__(self) -> None:
        self._real = LocalExtractor()

    async def extract(self, pages):
        result = await self._real.extract(pages)
        fields = dict(result.fields)
        original = fields.get("total_amount")
        if original:
            try:
                # "20.12" → "201.20" (10x slip)
                shifted = str(float(str(original).replace(",", "")) * 10)
                fields["total_amount"] = shifted
                print(f"  [slip injector] total_amount {original!r} → {shifted!r}")
            except (ValueError, TypeError):
                print(f"  [slip injector] could not parse total_amount={original!r}; leaving")
        return ExtractionResult(
            fields=fields,
            line_items=result.line_items,
            confidence=result.confidence,
            raw_text=result.raw_text,
            tier=result.tier,
        )


def _summarize(audit_log: list[dict]) -> None:
    print("\n--- TRACE ---")
    for i, entry in enumerate(audit_log, 1):
        icon = "✓" if entry.get("ok") else "✗"
        print(f"  {i:>2}. {icon} {entry.get('stage'):<12} reason={entry.get('reason')}")
        detail = entry.get("detail") or {}
        for k, v in detail.items():
            if k == "guidance_used" and isinstance(v, str):
                v = v[:140] + ("…" if len(v) > 140 else "")
            print(f"        {k}: {v}")


async def run(doc_id: str | None) -> None:
    if not os.getenv("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY not set — cannot exercise the Gemini path.", file=sys.stderr)
        sys.exit(2)

    db = SessionLocal()
    try:
        if doc_id:
            doc = db.query(Document).filter(Document.id == doc_id).first()
        else:
            doc = None
            for d in db.query(Document).limit(50).all():
                if os.path.exists(f"uploads/{d.filename}"):
                    doc = d
                    break
        if doc is None:
            print("No suitable document found.", file=sys.stderr)
            sys.exit(1)
        file_path = f"uploads/{doc.filename}"
        print(f"Forcing VLM reconciliation on {doc.id}  file={file_path}")
    finally:
        db.close()

    # Monkeypatch: the graph still runs the real ocr_node, but ocr_node
    # constructs _SlipInjector() instead of LocalExtractor().
    nodes.LocalExtractor = lambda *a, **kw: _SlipInjector()

    # Use the default production graph — we want every other node to be real.
    graph = build_graph()

    initial = AgentState(document_id=doc.id, file_path=file_path)
    t0 = time.perf_counter()
    final = await graph.ainvoke(initial)
    elapsed = time.perf_counter() - t0

    extracted = final.get("extracted_data") if isinstance(final, dict) else final.extracted_data
    tier = final.get("tier") if isinstance(final, dict) else final.tier
    is_valid = final.get("is_valid") if isinstance(final, dict) else final.is_valid
    attempts = final.get("attempts") if isinstance(final, dict) else final.attempts
    audit_log = final.get("audit_log") if isinstance(final, dict) else final.audit_log

    print(f"\n--- RESULT (elapsed {elapsed:.2f}s) ---")
    print(f"  is_valid:  {is_valid}")
    print(f"  tier:      {tier}")
    print(f"  attempts:  {attempts}")
    if extracted is not None:
        d = extracted.model_dump() if hasattr(extracted, "model_dump") else dict(extracted)
        print(f"  subtotal:     {d.get('subtotal')!r}")
        print(f"  tax:          {d.get('tax')!r}")
        print(f"  total_amount: {d.get('total_amount')!r}")

    _summarize(audit_log or [])


if __name__ == "__main__":
    doc_id = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run(doc_id))
