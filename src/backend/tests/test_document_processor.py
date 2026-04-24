from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.backend.extraction.local_extractor import LocalExtractorUnavailable
from src.backend.extraction.neural_fallback import NeuralUnavailableError
from src.backend.extraction.types import ExtractionResult
from src.backend.pipeline.document_processor import DocumentProcessor
from src.backend.pipeline.states import DocState


@dataclass
class FakeDoc:
    id: str = "doc_test_1"
    filename: str = "x.pdf"
    original_filename: str = "x.pdf"
    status: str = "uploaded"
    traceability_log: object = None
    fallback_tier: str | None = None
    confidence_score: float | None = None
    processed_at: object = None
    uploaded_at: object = None


class FakeDB:
    """Minimal SQLAlchemy session stand-in for unit tests."""

    def __init__(self, doc: FakeDoc) -> None:
        self.doc = doc
        self.committed = 0
        self._query_targets: list = []

    def query(self, model):
        self._query_targets.append(model)
        return FakeQuery()

    def commit(self):
        self.committed += 1

    def refresh(self, _):
        pass

    def add(self, _):
        pass


class FakeQuery:
    def filter(self, *_, **__):
        return self

    def delete(self):
        return 0

    def first(self):
        return None

    def all(self):
        return []

    def offset(self, _):
        return self

    def limit(self, _):
        return self


def _patch_crud(monkeypatch, db: FakeDB):
    from src.backend.pipeline import document_processor as dp

    def fake_get_document(_db, _id):
        return db.doc

    def fake_store_fields(_db, _id, payload):
        return [SimpleNamespace(id=f"fld_{i}") for i, _ in enumerate(payload)]

    def fake_store_line_items(_db, _id, payload):
        return [SimpleNamespace(id=f"lin_{i}") for i, _ in enumerate(payload)]

    def fake_update_status(_db, _id, status):
        db.doc.status = status

    monkeypatch.setattr(dp, "get_document", fake_get_document)
    monkeypatch.setattr(dp, "store_extracted_fields", fake_store_fields)
    monkeypatch.setattr(dp, "store_line_items", fake_store_line_items)
    monkeypatch.setattr(dp, "update_document_status", fake_update_status)
    monkeypatch.setattr(dp, "validate_document_fields", lambda _db, _id: [])


class FakeLocal:
    def __init__(self, result: ExtractionResult | Exception):
        self.result = result

    async def extract(self, pages):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeNeural:
    def __init__(self, result: ExtractionResult | Exception):
        self.result = result

    async def extract(self, image):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakePreprocessor:
    def preprocess_document(self, _):
        return [SimpleNamespace(page_number=1, processed=b"image", original=b"image")]


def _make_processor(local, neural, doc=None, monkeypatch=None):
    db = FakeDB(doc or FakeDoc())
    _patch_crud(monkeypatch, db)
    proc = DocumentProcessor(
        db=db,
        local=local,
        neural=neural,
        preprocessor=FakePreprocessor(),
        confidence_threshold=0.85,
    )
    return proc, db


def test_local_math_pass_verifies(monkeypatch):
    local_result = ExtractionResult(
        fields={
            "invoice_number": "INV-2025-0001",
            "date": "2025-01-15",
            "vendor_name": "Acme",
            "subtotal": "100",
            "tax": "15",
            "total_amount": "115",
        },
        confidence=0.95,
        tier="local",
    )
    proc, db = _make_processor(FakeLocal(local_result), FakeNeural(Exception("unused")), monkeypatch=monkeypatch)
    result = asyncio.run(proc.process("doc_test_1"))
    assert result["state"] == DocState.VERIFIED.value
    assert result["tier"] == "local"
    assert db.doc.fallback_tier == "local"


def test_local_math_fail_escalates_to_vlm(monkeypatch):
    local_bad = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "200"},
        confidence=0.95,
        tier="local",
    )
    vlm_good = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "115"},
        confidence=0.90,
        tier="vlm",
    )
    proc, db = _make_processor(FakeLocal(local_bad), FakeNeural(vlm_good), monkeypatch=monkeypatch)
    result = asyncio.run(proc.process("doc_test_1"))
    assert result["state"] == DocState.VERIFIED.value
    assert result["tier"] == "vlm"


def test_local_import_error_bypasses_to_vlm(monkeypatch):
    vlm_good = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "115"},
        confidence=0.90,
        tier="vlm",
    )
    proc, db = _make_processor(
        FakeLocal(LocalExtractorUnavailable("paddle missing")),
        FakeNeural(vlm_good),
        monkeypatch=monkeypatch,
    )
    result = asyncio.run(proc.process("doc_test_1"))
    assert result["state"] == DocState.VERIFIED.value
    assert result["tier"] == "vlm"
    reasons = [e["reason"] for e in result["trace"]]
    assert "local_import_error" in reasons


def test_both_tiers_fail_flags_not_crashes(monkeypatch):
    proc, db = _make_processor(
        FakeLocal(LocalExtractorUnavailable("paddle missing")),
        FakeNeural(NeuralUnavailableError("no api key")),
        monkeypatch=monkeypatch,
    )
    result = asyncio.run(proc.process("doc_test_1"))
    assert result["state"] == DocState.FLAGGED.value
    assert result["tier"] == "local_degraded"


def test_empty_local_extraction_escalates(monkeypatch):
    empty_local = ExtractionResult(fields={"invoice_number": None, "total_amount": None}, confidence=0.5)
    vlm_good = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "115"},
        confidence=0.90,
    )
    proc, db = _make_processor(FakeLocal(empty_local), FakeNeural(vlm_good), monkeypatch=monkeypatch)
    result = asyncio.run(proc.process("doc_test_1"))
    reasons = [e["reason"] for e in result["trace"]]
    assert "local_empty_extraction" in reasons
    assert result["state"] == DocState.VERIFIED.value
    assert result["tier"] == "vlm"


def test_low_confidence_escalates(monkeypatch):
    low_conf = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "115"},
        confidence=0.40,
    )
    vlm_good = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "115"},
        confidence=0.95,
    )
    proc, _ = _make_processor(FakeLocal(low_conf), FakeNeural(vlm_good), monkeypatch=monkeypatch)
    result = asyncio.run(proc.process("doc_test_1"))
    assert result["tier"] == "vlm"


def test_vlm_audit_fail_flags(monkeypatch):
    local_bad = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "200"},
        confidence=0.95,
    )
    vlm_bad = ExtractionResult(
        fields={"subtotal": "100", "tax": "15", "total_amount": "300"},
        confidence=0.90,
    )
    proc, _ = _make_processor(FakeLocal(local_bad), FakeNeural(vlm_bad), monkeypatch=monkeypatch)
    result = asyncio.run(proc.process("doc_test_1"))
    assert result["state"] == DocState.FLAGGED.value
    assert result["tier"] == "vlm"
