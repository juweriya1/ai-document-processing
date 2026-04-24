"""Tier-1 smoke: run PaddleOCR + layout-aware heuristics on a PDF and print fields."""
from __future__ import annotations

import asyncio
import json
import sys

from src.backend.extraction.local_extractor import LocalExtractor
from src.backend.ingestion.preprocessing import Preprocessing
from src.backend.validation.auditor import FinancialAuditor


async def run(pdf_path: str) -> None:
    pages = Preprocessing().preprocess_document(pdf_path)
    print(f"pages: {len(pages)}")
    extractor = LocalExtractor()
    result = await extractor.extract(pages)
    print("FIELDS:")
    print(json.dumps(result.fields, indent=2))
    print(f"CONFIDENCE: {result.confidence}")
    print("RAW (first 2000 chars):")
    print(result.raw_text[:2000])
    audit = FinancialAuditor().audit(result.fields)
    print("AUDIT:")
    print(
        json.dumps(
            {
                "ok": audit.ok,
                "total": str(audit.total) if audit.total else None,
                "subtotal": str(audit.subtotal) if audit.subtotal else None,
                "tax": str(audit.tax) if audit.tax else None,
                "delta": str(audit.delta) if audit.delta else None,
                "reason": audit.reason,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "uploads/doc_468b24dbdb75.pdf"
    asyncio.run(run(path))
