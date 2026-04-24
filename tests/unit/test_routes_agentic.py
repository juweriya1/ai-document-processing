"""Integration tests for /api/agentic/{id}/process and /status.

Verifies the FastAPI route end-to-end with the real TestClient stack:
- JWT Bearer auth enforcement (401 without, 403 with wrong role)
- 404 on unknown document_id
- Response shape matches the React frontend contract exactly — specifically
  ProcessingPage.handleProcess reads `document_id`, `status`, `fields_extracted`,
  `line_items_extracted`, and the stepper accepts only
  {'preprocessing','extracting','validating','review_pending','approved','rejected','failed'}
- DocState.VERIFIED is translated to "review_pending" on the wire so the
  frontend stepper / nav buttons behave correctly for agentic runs
- Agentic extensions (`is_valid`, `tier`, `attempts`, `trace`, `extracted_data`)
  are additive and present so a future richer UI can consume them

The compiled LangGraph is stubbed via monkeypatch so these tests exercise
only the HTTP plumbing (routing, auth, response shape). Graph-internal
behavior has its own tests in src/backend/tests/test_agent_graph.py.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.agents.state import AgentState, ExtractedInvoice, LineItem
from src.backend.api import routes_agentic
from src.backend.auth.jwt_handler import create_access_token
from src.backend.config import TEST_DATABASE_URL
from src.backend.db.crud import create_document
from src.backend.db.database import get_db
from src.backend.db.models import Base, Document
from src.backend.main import app
from src.backend.pipeline.document_processor import TraceEntry
from src.backend.pipeline.reason_codes import ReasonCode
from src.backend.pipeline.states import DocState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def enterprise_token():
    return create_access_token(
        data={"sub": "user@test.com", "role": "enterprise_user", "user_id": "usr_ent001"}
    )


@pytest.fixture
def reviewer_token():
    return create_access_token(
        data={"sub": "reviewer@test.com", "role": "reviewer", "user_id": "usr_rev001"}
    )


@pytest.fixture
def wrong_role_token():
    # A role that is NOT in the route's allowed list — should get 403.
    return create_access_token(
        data={"sub": "intern@test.com", "role": "intern", "user_id": "usr_int001"}
    )


@pytest.fixture
def test_document(test_db):
    return create_document(
        test_db,
        filename="agentic_test.pdf",
        original_filename="agentic_test.pdf",
        file_type="application/pdf",
        file_size=4096,
    )


class _StubGraph:
    """Captures the initial state and returns a pre-programmed final state.

    Mirrors the minimal surface LangGraph's CompiledStateGraph exposes that
    routes_agentic.process_document_agentic depends on — just the async
    .ainvoke(initial) contract.
    """

    def __init__(self, final_state: dict) -> None:
        self._final = final_state
        self.last_initial: AgentState | None = None
        self.call_count = 0

    async def ainvoke(self, initial: AgentState) -> dict:
        self.last_initial = initial
        self.call_count += 1
        return self._final


def _verified_final_state(document_id: str) -> dict:
    """Graph final state after a clean Tier-1 verification."""
    return {
        "document_id": document_id,
        "file_path": f"uploads/agentic_test.pdf",
        "pages": None,
        "extracted_data": ExtractedInvoice(
            invoice_number="INV-5001",
            date="2026-04-24",
            vendor_name="Acme Corp",
            subtotal="200.00",
            tax="30.00",
            total_amount="230.00",
            line_items=[LineItem(description="Widget", quantity="2", unit_price="100.00", total="200.00")],
        ),
        "audit_log": [
            asdict(TraceEntry.now("preprocess", DocState.PREPROCESSED, True, page_count=1)),
            asdict(TraceEntry.now("ocr", DocState.LOCALLY_PARSED, True,
                                  reason=ReasonCode.LOCAL_OK, confidence=0.91)),
            asdict(TraceEntry.now("audit", DocState.LOCALLY_PARSED, True,
                                  reason=ReasonCode.LOCAL_OK,
                                  subtotal="200.00", tax="30.00", total="230.00", delta="0.00")),
        ],
        "attempts": 0,
        "is_valid": True,
        "tier": "local",
        "reason": "local_ok",
        "reconciliation_guidance": None,
    }


def _vlm_reconciled_final_state(document_id: str) -> dict:
    """Graph final state after one Gemini reconciliation that corrected a slip."""
    s = _verified_final_state(document_id)
    s["tier"] = "vlm"
    s["attempts"] = 1
    s["reason"] = "vlm_retried"
    # Extra trace entries for the reconcile→re-audit loop.
    s["audit_log"].append(asdict(TraceEntry.now(
        "reconcile", DocState.VLM_RECONCILED, True,
        reason=ReasonCode.VLM_RETRIED, attempt=0, confidence=0.86,
    )))
    s["audit_log"].append(asdict(TraceEntry.now(
        "audit", DocState.LOCALLY_PARSED, True,
        reason=ReasonCode.LOCAL_OK, attempt=1,
    )))
    return s


def _preprocess_failed_final_state(document_id: str) -> dict:
    return {
        "document_id": document_id,
        "file_path": f"uploads/agentic_test.pdf",
        "pages": None,
        "extracted_data": None,
        "audit_log": [
            asdict(TraceEntry.now(
                "preprocess", DocState.FAILED, False,
                reason=ReasonCode.PREPROCESS_FAIL,
                error="file_not_found: uploads/agentic_test.pdf",
            )),
        ],
        "attempts": 0,
        "is_valid": False,
        "tier": "hitl",
        "reason": "preprocess_fail",
        "reconciliation_guidance": None,
    }


def _install_graph(monkeypatch, final_state: dict) -> _StubGraph:
    stub = _StubGraph(final_state)
    monkeypatch.setattr(routes_agentic, "compiled_graph", stub)
    return stub


# ---------------------------------------------------------------------------
# POST /api/agentic/{document_id}/process
# ---------------------------------------------------------------------------


class TestProcessAgenticAuth:
    def test_no_auth_header_returns_401(self, client, test_document):
        resp = client.post(f"/api/agentic/{test_document.id}/process")
        assert resp.status_code == 401

    def test_malformed_auth_header_returns_401(self, client, test_document):
        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": "NotBearer xyz"},
        )
        assert resp.status_code == 401

    def test_wrong_role_returns_403(self, client, test_document, wrong_role_token, monkeypatch):
        # Install a stub so the test fails fast if the route erroneously
        # lets an unauthorized caller through to graph execution.
        _install_graph(monkeypatch, _verified_final_state(test_document.id))
        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": f"Bearer {wrong_role_token}"},
        )
        assert resp.status_code == 403
        assert "permissions" in resp.json().get("detail", "").lower()

    def test_document_not_found_returns_404(self, client, enterprise_token, monkeypatch):
        _install_graph(monkeypatch, _verified_final_state("doc_does_not_exist"))
        resp = client.post(
            "/api/agentic/doc_does_not_exist/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 404


class TestProcessAgenticResponseContract:
    """Response must match what ProcessingPage.handleProcess reads."""

    REQUIRED_FRONTEND_KEYS = {
        "document_id",
        "status",
        "fields_extracted",
        "line_items_extracted",
    }

    AGENTIC_EXTENSION_KEYS = {
        "is_valid",
        "tier",
        "attempts",
        "last_reason",
        "extracted_data",
        "trace",
        "trace_length",
    }

    # The React ProcessingPage stepper only knows these states. A response
    # outside this set would render the stepper as all-pending and hide the
    # nav buttons — i.e. a silent UX break.
    FRONTEND_KNOWN_STATUSES = {
        "uploaded",
        "preprocessing",
        "extracting",
        "validating",
        "review_pending",
        "approved",
        "rejected",
        "failed",
    }

    def test_verified_graph_run_returns_frontend_contract(
        self, client, enterprise_token, test_document, monkeypatch,
    ):
        stub = _install_graph(monkeypatch, _verified_final_state(test_document.id))

        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        data = resp.json()

        # Frontend contract (ProcessingPage.handleProcess reads these):
        assert self.REQUIRED_FRONTEND_KEYS.issubset(data.keys()), (
            f"Response is missing keys ProcessingPage depends on. "
            f"Got {sorted(data.keys())}"
        )
        assert data["document_id"] == test_document.id
        assert data["status"] in self.FRONTEND_KNOWN_STATUSES, (
            f"status={data['status']!r} is not a stepper-known value; "
            f"frontend would render all steps as 'pending'"
        )
        assert isinstance(data["fields_extracted"], int)
        assert isinstance(data["line_items_extracted"], int)

        # Agentic extensions — additive for future richer UI.
        assert self.AGENTIC_EXTENSION_KEYS.issubset(data.keys())

        # Graph was called exactly once with the right initial state.
        assert stub.call_count == 1
        assert stub.last_initial is not None
        assert stub.last_initial.document_id == test_document.id
        assert stub.last_initial.file_path.endswith(test_document.filename)

    def test_verified_run_maps_status_to_review_pending(
        self, client, enterprise_token, test_document, monkeypatch,
    ):
        """DocState.VERIFIED must surface as 'review_pending' on the wire so
        the frontend stepper lands on the final step and the nav buttons
        (View Validation / Go to Review) appear. 'verified' is NOT in the
        stepper's known vocabulary."""
        _install_graph(monkeypatch, _verified_final_state(test_document.id))
        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True, "precondition: graph returned is_valid=True"
        assert data["status"] == "review_pending"

    def test_fields_and_line_items_counts_reflect_extracted_data(
        self, client, enterprise_token, test_document, monkeypatch,
    ):
        _install_graph(monkeypatch, _verified_final_state(test_document.id))
        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        data = resp.json()
        # The stub invoice has 6 populated top-level fields and 1 line item.
        assert data["fields_extracted"] == 6
        assert data["line_items_extracted"] == 1

    def test_extracted_data_shape_matches_invoice_model(
        self, client, enterprise_token, test_document, monkeypatch,
    ):
        _install_graph(monkeypatch, _verified_final_state(test_document.id))
        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        extracted = resp.json()["extracted_data"]
        assert extracted is not None
        for key in ("invoice_number", "date", "vendor_name",
                    "subtotal", "tax", "total_amount", "line_items"):
            assert key in extracted, f"extracted_data missing {key!r}"
        assert extracted["line_items"][0]["description"] == "Widget"

    def test_vlm_reconciled_run_reports_tier_and_attempts(
        self, client, reviewer_token, test_document, monkeypatch,
    ):
        _install_graph(monkeypatch, _vlm_reconciled_final_state(test_document.id))
        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        data = resp.json()
        assert data["status"] == "review_pending"
        assert data["is_valid"] is True
        assert data["tier"] == "vlm"
        assert data["attempts"] == 1
        # Trace carries the full story of the reconciliation loop.
        stages = [e["stage"] for e in data["trace"]]
        assert "reconcile" in stages
        assert data["trace_length"] == len(data["trace"])

    def test_preprocess_failure_surfaces_as_failed_status(
        self, client, enterprise_token, test_document, monkeypatch,
    ):
        """Preprocess-level failure (unreadable PDF, missing file) should not
        push the user to 'Go to Review' — there's nothing to review. Must
        surface as 'failed' so the frontend stepper marks the pipeline as
        broken and shows the error state."""
        _install_graph(monkeypatch, _preprocess_failed_final_state(test_document.id))
        resp = client.post(
            f"/api/agentic/{test_document.id}/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        data = resp.json()
        assert data["status"] == "failed"
        assert data["is_valid"] is False
        assert data["fields_extracted"] == 0
        assert data["line_items_extracted"] == 0


# ---------------------------------------------------------------------------
# GET /api/agentic/{document_id}/status
# ---------------------------------------------------------------------------


class TestAgenticStatus:
    def test_no_auth_returns_401(self, client, test_document):
        resp = client.get(f"/api/agentic/{test_document.id}/status")
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, enterprise_token):
        resp = client.get(
            "/api/agentic/doc_nope/status",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 404

    def test_status_shape_matches_frontend_expectations(
        self, client, enterprise_token, test_document, test_db,
    ):
        # Simulate a completed agentic run landing in the DB.
        test_document.status = "verified"
        test_document.fallback_tier = "vlm"
        test_document.confidence_score = 0.88
        test_document.traceability_log = [{"stage": "audit", "ok": True}]
        test_db.commit()

        resp = client.get(
            f"/api/agentic/{test_document.id}/status",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Frontend ProcessingPage + ReviewPage both read these:
        assert data["document_id"] == test_document.id
        assert data["filename"] == test_document.original_filename
        # "verified" at DB → "review_pending" at the wire for stepper compat.
        assert data["status"] == "review_pending"
        # Agentic fields (used by future richer UI and the audit dashboard):
        assert data["fallback_tier"] == "vlm"
        assert data["confidence_score"] == 0.88
        assert isinstance(data["traceability_log"], list)
        assert data["uploaded_at"] is not None

    def test_status_passes_through_known_frontend_values(
        self, client, enterprise_token, test_document, test_db,
    ):
        """Statuses already in the frontend's vocabulary must not be rewritten."""
        test_document.status = "review_pending"
        test_db.commit()
        resp = client.get(
            f"/api/agentic/{test_document.id}/status",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.json()["status"] == "review_pending"
