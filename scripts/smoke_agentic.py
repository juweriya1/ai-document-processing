"""End-to-end smoke test for the Agentic Financial Auditor.

Picks one real document from the Postgres `documents` table, runs the compiled
LangGraph against its PDF on disk, and prints a structured report of what
happened at each node — what the auditor decided, whether Gemini was invoked,
and what the final DB row looks like afterwards.

Usage:
    .venv/bin/python scripts/smoke_agentic.py [document_id]

If document_id is omitted, the first review_pending doc with a file on disk
is used.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

from src.backend.agents.graph import compiled_graph
from src.backend.agents.state import AgentState
from src.backend.db.database import SessionLocal
from src.backend.db.models import Document


def _pick_doc(db, requested_id: str | None) -> Document | None:
    if requested_id:
        return db.query(Document).filter(Document.id == requested_id).first()
    for doc in db.query(Document).limit(50).all():
        if os.path.exists(f"uploads/{doc.filename}"):
            return doc
    return None


def _summarize_trace(audit_log: list[dict]) -> None:
    print("\n--- TRACE ---")
    for i, entry in enumerate(audit_log, 1):
        stage = entry.get("stage")
        ok = entry.get("ok")
        reason = entry.get("reason")
        detail = entry.get("detail") or {}
        status_icon = "✓" if ok else "✗"
        print(f"  {i:>2}. {status_icon} {stage:<12} reason={reason}")
        for k, v in detail.items():
            if k == "guidance_used" and isinstance(v, str):
                v = v[:120] + ("…" if len(v) > 120 else "")
            print(f"        {k}: {v}")


async def run(doc_id: str | None) -> None:
    db = SessionLocal()
    try:
        doc = _pick_doc(db, doc_id)
        if doc is None:
            print("No suitable document found. Upload one first.", file=sys.stderr)
            sys.exit(1)
        file_path = f"uploads/{doc.filename}"
        print(f"Running agentic graph on {doc.id} ({doc.original_filename or doc.filename})")
        print(f"  file: {file_path}  ({os.path.getsize(file_path):,} bytes)")
        print(f"  pre-run status: {doc.status}")
    finally:
        db.close()

    initial = AgentState(document_id=doc.id, file_path=file_path)

    t0 = time.perf_counter()
    final = await compiled_graph.ainvoke(initial)
    elapsed = time.perf_counter() - t0

    # LangGraph returns a dict when the state schema is a Pydantic model.
    extracted = final.get("extracted_data") if isinstance(final, dict) else final.extracted_data
    tier = final.get("tier") if isinstance(final, dict) else final.tier
    is_valid = final.get("is_valid") if isinstance(final, dict) else final.is_valid
    attempts = final.get("attempts") if isinstance(final, dict) else final.attempts
    reason = final.get("reason") if isinstance(final, dict) else final.reason
    audit_log = final.get("audit_log") if isinstance(final, dict) else final.audit_log

    print(f"\n--- RESULT (elapsed {elapsed:.2f}s) ---")
    print(f"  is_valid:  {is_valid}")
    print(f"  tier:      {tier}")
    print(f"  attempts:  {attempts}")
    print(f"  reason:    {reason}")
    if extracted is not None:
        data = extracted.model_dump() if hasattr(extracted, "model_dump") else dict(extracted)
        print(f"  fields:")
        for k in ("invoice_number", "date", "vendor_name", "subtotal", "tax", "total_amount"):
            print(f"    {k}: {data.get(k)!r}")
        line_items = data.get("line_items") or []
        print(f"  line_items: {len(line_items)}")
        for li in line_items[:5]:
            if hasattr(li, "model_dump"):
                li = li.model_dump()
            print(f"    - {li}")
    else:
        print("  extracted_data: None")

    _summarize_trace(audit_log or [])

    # Confirm the DB was actually updated.
    db = SessionLocal()
    try:
        refreshed = db.query(Document).filter(Document.id == doc.id).first()
        print(f"\n--- DB after run ---")
        print(f"  status:            {refreshed.status}")
        print(f"  fallback_tier:     {refreshed.fallback_tier}")
        print(f"  confidence_score:  {refreshed.confidence_score}")
        print(f"  traceability_log:  {'populated (' + str(len(refreshed.traceability_log or [])) + ' entries)' if refreshed.traceability_log else 'NULL'}")
        print(f"  processed_at:      {refreshed.processed_at}")
    finally:
        db.close()


if __name__ == "__main__":
    doc_id = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run(doc_id))
