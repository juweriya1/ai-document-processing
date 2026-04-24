"""Unit tests for the batch fan-out worker + batch finalization.

Verifies:
- The Semaphore bound holds: concurrent _process_one calls cap at
  BATCH_CONCURRENCY so a 10-doc batch never runs 10 graph invocations at once.
- Per-doc failure isolation: a graph exception on one doc sets its status to
  "failed" without affecting sibling tasks.
- _maybe_finalize_batch transitions:
  - Any doc still running → no state change.
  - All terminal + none failed → "completed".
  - All terminal + any failed → "partial_failed".
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.api import routes_batch
from src.backend.config import TEST_DATABASE_URL
from src.backend.db.crud import create_batch, create_document, get_batch
from src.backend.db.database import SessionLocal
from src.backend.db.models import Base, Document, User


@pytest.fixture
def test_engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(test_engine):
    Session = sessionmaker(bind=test_engine)
    s = Session()
    # Seed the FK referenced by all tests (Batch.created_by, Document.uploaded_by).
    s.add(User(id="usr_1", email="usr_1@test.com", password_hash="stub",
              name="usr_1", role="enterprise_user"))
    s.commit()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def patched_session_local(monkeypatch, test_engine):
    """Redirect routes_batch.SessionLocal to the test engine so background
    tasks read/write the same DB as the pytest fixture."""
    TestSession = sessionmaker(bind=test_engine)
    monkeypatch.setattr(routes_batch, "SessionLocal", TestSession)
    return TestSession


def test_maybe_finalize_batch_leaves_running_batch_alone(db):
    batch = create_batch(db, created_by="usr_1", total_documents=2, status="processing")
    d1 = create_document(
        db, filename="a.pdf", original_filename="a.pdf",
        file_type="application/pdf", file_size=100,
        uploaded_by="usr_1", batch_id=batch.id,
    )
    d1.status = "verified"
    d2 = create_document(
        db, filename="b.pdf", original_filename="b.pdf",
        file_type="application/pdf", file_size=100,
        uploaded_by="usr_1", batch_id=batch.id,
    )
    d2.status = "processing"  # still in flight
    db.commit()

    routes_batch._maybe_finalize_batch(db, batch.id)
    db.refresh(batch)
    assert batch.status == "processing"


def test_maybe_finalize_batch_marks_completed_on_all_terminal_success(db):
    batch = create_batch(db, created_by="usr_1", total_documents=2, status="processing")
    for name, st in [("a.pdf", "verified"), ("b.pdf", "approved")]:
        d = create_document(
            db, filename=name, original_filename=name,
            file_type="application/pdf", file_size=100,
            uploaded_by="usr_1", batch_id=batch.id,
        )
        d.status = st
    db.commit()

    routes_batch._maybe_finalize_batch(db, batch.id)
    db.refresh(batch)
    assert batch.status == "completed"


def test_maybe_finalize_batch_marks_partial_failed_when_any_failed(db):
    batch = create_batch(db, created_by="usr_1", total_documents=3, status="processing")
    for name, st in [("a.pdf", "verified"), ("b.pdf", "failed"), ("c.pdf", "review_pending")]:
        d = create_document(
            db, filename=name, original_filename=name,
            file_type="application/pdf", file_size=100,
            uploaded_by="usr_1", batch_id=batch.id,
        )
        d.status = st
    db.commit()

    routes_batch._maybe_finalize_batch(db, batch.id)
    db.refresh(batch)
    assert batch.status == "partial_failed"


def test_maybe_finalize_batch_is_noop_when_already_terminal(db):
    batch = create_batch(db, created_by="usr_1", total_documents=1, status="completed")
    d = create_document(
        db, filename="a.pdf", original_filename="a.pdf",
        file_type="application/pdf", file_size=100,
        uploaded_by="usr_1", batch_id=batch.id,
    )
    d.status = "verified"
    db.commit()

    routes_batch._maybe_finalize_batch(db, batch.id)
    db.refresh(batch)
    # Still "completed" — no regression back to "processing" or similar.
    assert batch.status == "completed"


# ---------------------------------------------------------------------------
# _process_one behavior — semaphore + failure isolation
# ---------------------------------------------------------------------------


class _StubGraph:
    """Controllable graph stub for concurrency/isolation tests.

    Records the count of in-flight invocations via an asyncio.Event/Lock
    pattern so the test can observe that the semaphore bound is honored.
    """

    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0
        self.lock = asyncio.Lock()
        self.release_event = asyncio.Event()
        self.fail_for: set[str] = set()

    async def ainvoke(self, initial) -> dict:
        async with self.lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await self.release_event.wait()
            if initial.document_id in self.fail_for:
                raise RuntimeError(f"simulated_graph_failure: {initial.document_id}")
            # Simulate successful run: mark doc as verified via a separate session
            # since persist_node would normally handle this.
            S = routes_batch.SessionLocal()
            try:
                doc = S.query(Document).filter(Document.id == initial.document_id).first()
                if doc is not None:
                    doc.status = "verified"
                    S.commit()
            finally:
                S.close()
            return {}
        finally:
            async with self.lock:
                self.in_flight -= 1


def test_process_one_success_updates_doc_to_verified(db, patched_session_local, monkeypatch):
    stub = _StubGraph()
    stub.release_event.set()  # don't block
    monkeypatch.setattr(routes_batch, "compiled_graph", stub)

    batch = create_batch(db, created_by="usr_1", total_documents=1, status="processing")
    doc = create_document(
        db, filename="a.pdf", original_filename="a.pdf",
        file_type="application/pdf", file_size=100,
        uploaded_by="usr_1", batch_id=batch.id,
    )
    db.commit()

    asyncio.run(routes_batch._process_one(doc.id))

    db.refresh(doc)
    db.refresh(batch)
    assert doc.status == "verified"
    # Single doc terminal success → batch finalized to "completed".
    assert batch.status == "completed"


def test_process_one_failure_marks_doc_failed_and_partial_fails_batch(
    db, patched_session_local, monkeypatch
):
    stub = _StubGraph()
    stub.release_event.set()
    monkeypatch.setattr(routes_batch, "compiled_graph", stub)

    batch = create_batch(db, created_by="usr_1", total_documents=2, status="processing")
    doc_ok = create_document(
        db, filename="ok.pdf", original_filename="ok.pdf",
        file_type="application/pdf", file_size=100,
        uploaded_by="usr_1", batch_id=batch.id,
    )
    doc_bad = create_document(
        db, filename="bad.pdf", original_filename="bad.pdf",
        file_type="application/pdf", file_size=100,
        uploaded_by="usr_1", batch_id=batch.id,
    )
    db.commit()
    stub.fail_for.add(doc_bad.id)

    async def run_both():
        await asyncio.gather(
            routes_batch._process_one(doc_ok.id),
            routes_batch._process_one(doc_bad.id),
        )
    asyncio.run(run_both())

    db.refresh(doc_ok)
    db.refresh(doc_bad)
    db.refresh(batch)
    assert doc_ok.status == "verified"
    assert doc_bad.status == "failed"
    assert "agent_execution_failed" in (doc_bad.rejected_reason or "")
    assert batch.status == "partial_failed"


def test_process_one_semaphore_bounds_concurrency(
    db, patched_session_local, monkeypatch
):
    """Schedule 6 doc runs with concurrency=2; max_in_flight must never exceed 2."""
    # Swap the module-level semaphore for a fresh one we control the width of.
    monkeypatch.setattr(routes_batch, "_batch_semaphore", asyncio.Semaphore(2))

    stub = _StubGraph()
    monkeypatch.setattr(routes_batch, "compiled_graph", stub)

    batch = create_batch(db, created_by="usr_1", total_documents=6, status="processing")
    doc_ids: list[str] = []
    for i in range(6):
        d = create_document(
            db, filename=f"d{i}.pdf", original_filename=f"d{i}.pdf",
            file_type="application/pdf", file_size=100,
            uploaded_by="usr_1", batch_id=batch.id,
        )
        doc_ids.append(d.id)
    db.commit()

    async def runner():
        tasks = [asyncio.create_task(routes_batch._process_one(d)) for d in doc_ids]
        # Let 2 tasks reach the lock-protected "in_flight" increment, then release.
        await asyncio.sleep(0.05)
        stub.release_event.set()
        await asyncio.gather(*tasks)

    asyncio.run(runner())
    assert stub.max_in_flight <= 2, (
        f"semaphore breach: max_in_flight={stub.max_in_flight}, expected <=2"
    )
    assert stub.max_in_flight >= 1  # sanity: at least one ran
