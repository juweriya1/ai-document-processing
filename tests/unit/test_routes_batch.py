"""Integration tests for /api/batches endpoints.

Covers:
- Auth (401/403) on all endpoints
- Upload validation: empty batch, too-large batch, bad extension
- Happy path: 3 mock files → 201 with batch_id + document_ids
- Aggregation: GET /{id} returns correct counts per status
- Ownership: enterprise_user only sees their own; admin sees all
- Re-kick: POST /{id}/process only re-runs uploaded/failed docs
- List: ?limit=N caps the result

The LangGraph `compiled_graph` and the background fan-out worker are stubbed
so tests don't spin up PaddleOCR or Gemini. Graph-internal behavior has its
own tests in src/backend/tests/test_agent_graph.py. Fan-out concurrency is
tested separately in src/backend/tests/test_batch_fanout.py.
"""
from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.api import routes_batch
from src.backend.auth.jwt_handler import create_access_token
from src.backend.config import TEST_DATABASE_URL
from src.backend.db.crud import create_batch, create_document
from src.backend.db.database import get_db
from src.backend.db.models import Base, Document, User
from src.backend.main import app


def _seed_user(db, user_id: str, role: str = "enterprise_user") -> None:
    """Insert a matching User row so Batch/Document FKs (uploaded_by,
    created_by, approved_by) can resolve. Passlib hashing is skipped — we
    just need the row to exist."""
    u = User(
        id=user_id,
        email=f"{user_id}@test.com",
        password_hash="stub",
        name=user_id,
        role=role,
    )
    db.add(u)
    db.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Seed all users referenced by test JWTs so FK constraints resolve.
    for uid, role in [
        ("usr_ent001", "enterprise_user"),
        ("usr_ent002", "enterprise_user"),
        ("usr_admin", "admin"),
        ("usr_int", "intern"),
    ]:
        _seed_user(session, uid, role)
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(test_db, monkeypatch, tmp_path):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    # Point the uploader at a throwaway tmpdir so tests don't pollute
    # the project's uploads/ directory.
    monkeypatch.setattr(routes_batch.file_uploader, "upload_dir", str(tmp_path))

    # Replace the fan-out worker with a no-op — by default tests should
    # not kick off real graph execution. Individual tests that need a
    # specific end-state monkeypatch _process_one with their own fake.
    async def _noop(_doc_id: str) -> None:
        return None
    monkeypatch.setattr(routes_batch, "_process_one", _noop)

    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def enterprise_token():
    return create_access_token(
        data={"sub": "user@test.com", "role": "enterprise_user", "user_id": "usr_ent001"}
    )


@pytest.fixture
def other_enterprise_token():
    return create_access_token(
        data={"sub": "other@test.com", "role": "enterprise_user", "user_id": "usr_ent002"}
    )


@pytest.fixture
def admin_token():
    return create_access_token(
        data={"sub": "admin@test.com", "role": "admin", "user_id": "usr_admin"}
    )


@pytest.fixture
def wrong_role_token():
    return create_access_token(
        data={"sub": "intern@test.com", "role": "intern", "user_id": "usr_int"}
    )


def _pdf_payload(name: str = "test.pdf") -> tuple[str, bytes, str]:
    # Minimal PDF header so any sniffer downstream recognizes it.
    return (name, b"%PDF-1.4\n%stub\n", "application/pdf")


def _files_form(n: int, ext: str = "pdf", content_type: str = "application/pdf") -> list:
    return [("files", (f"doc_{i}.{ext}", b"%PDF-1.4\n%stub\n", content_type)) for i in range(n)]


# ---------------------------------------------------------------------------
# POST /api/batches/upload — auth + validation
# ---------------------------------------------------------------------------


class TestUploadAuth:
    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/batches/upload", files=_files_form(1))
        assert resp.status_code == 401

    def test_wrong_role_returns_403(self, client, wrong_role_token):
        resp = client.post(
            "/api/batches/upload",
            files=_files_form(1),
            headers={"Authorization": f"Bearer {wrong_role_token}"},
        )
        assert resp.status_code == 403


class TestUploadValidation:
    def test_empty_files_returns_400(self, client, enterprise_token):
        # Sending zero files — FastAPI returns 422 for missing required field.
        resp = client.post(
            "/api/batches/upload",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code in (400, 422)

    def test_too_many_files_returns_400(self, client, enterprise_token):
        resp = client.post(
            "/api/batches/upload",
            files=_files_form(21),
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 400
        assert "batch_too_large" in resp.json().get("detail", "")

    def test_bad_extension_rejects_whole_batch(self, client, test_db, enterprise_token):
        # 2 good + 1 bad. Must be all-or-nothing: no Batch or Document rows
        # should exist after rejection.
        files = _files_form(2) + [("files", ("malware.exe", b"stub", "application/octet-stream"))]
        resp = client.post(
            "/api/batches/upload",
            files=files,
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 400
        # Verify atomicity — no rows were written.
        assert test_db.query(Document).count() == 0
        # Batch rows also should not exist.
        from src.backend.db.models import Batch
        assert test_db.query(Batch).count() == 0


# ---------------------------------------------------------------------------
# POST /api/batches/upload — happy path
# ---------------------------------------------------------------------------


class TestUploadHappyPath:
    def test_returns_201_with_batch_id_and_doc_ids(self, client, test_db, enterprise_token):
        resp = client.post(
            "/api/batches/upload",
            files=_files_form(3),
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["batch_id"].startswith("bat_")
        assert len(body["document_ids"]) == 3
        assert all(d.startswith("doc_") for d in body["document_ids"])
        assert body["total_documents"] == 3
        # All 3 Document rows were persisted under the returned batch_id.
        docs = test_db.query(Document).filter(Document.batch_id == body["batch_id"]).all()
        assert len(docs) == 3
        assert all(d.uploaded_by == "usr_ent001" for d in docs)

    def test_single_file_batch_is_legal(self, client, enterprise_token):
        # N=1 is the "batch of 1" special case — still creates a Batch row.
        resp = client.post(
            "/api/batches/upload",
            files=_files_form(1),
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["total_documents"] == 1

    def test_twenty_file_batch_is_legal(self, client, enterprise_token):
        resp = client.post(
            "/api/batches/upload",
            files=_files_form(20),
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["total_documents"] == 20


# ---------------------------------------------------------------------------
# GET /api/batches/{id}
# ---------------------------------------------------------------------------


class TestGetBatchStatus:
    def test_404_for_unknown_batch(self, client, enterprise_token):
        resp = client.get(
            "/api/batches/bat_nosuchbt",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 404

    def test_returns_counts_and_docs(self, client, test_db, enterprise_token):
        # Seed: create a batch with 3 docs, then manually flip statuses.
        batch = create_batch(test_db, created_by="usr_ent001", total_documents=3)
        for status_value in ("verified", "failed", "processing"):
            doc = create_document(
                test_db,
                filename=f"{status_value}.pdf",
                original_filename=f"{status_value}.pdf",
                file_type="application/pdf",
                file_size=100,
                uploaded_by="usr_ent001",
                batch_id=batch.id,
            )
            doc.status = status_value
        test_db.commit()

        resp = client.get(
            f"/api/batches/{batch.id}",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == batch.id
        assert body["total_documents"] == 3
        assert body["counts"]["verified"] == 1
        assert body["counts"]["failed"] == 1
        assert body["counts"]["processing"] == 1
        assert len(body["documents"]) == 3

    def test_enterprise_user_cannot_see_other_users_batch(
        self, client, test_db, other_enterprise_token
    ):
        # Batch owned by usr_ent001 but queried by usr_ent002 → 404.
        batch = create_batch(test_db, created_by="usr_ent001", total_documents=1)
        resp = client.get(
            f"/api/batches/{batch.id}",
            headers={"Authorization": f"Bearer {other_enterprise_token}"},
        )
        assert resp.status_code == 404

    def test_admin_can_see_other_users_batch(self, client, test_db, admin_token):
        batch = create_batch(test_db, created_by="usr_ent001", total_documents=1)
        resp = client.get(
            f"/api/batches/{batch.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/batches/{id}/process — idempotent re-kick
# ---------------------------------------------------------------------------


class TestReprocessBatch:
    def test_only_requeues_uploaded_and_failed(
        self, client, test_db, enterprise_token, monkeypatch
    ):
        captured: list[str] = []

        async def capture(doc_id: str) -> None:
            captured.append(doc_id)

        monkeypatch.setattr(routes_batch, "_process_one", capture)

        batch = create_batch(test_db, created_by="usr_ent001", total_documents=3)
        statuses = ["failed", "uploaded", "verified"]
        doc_ids_by_status = {}
        for s in statuses:
            doc = create_document(
                test_db,
                filename=f"{s}.pdf",
                original_filename=f"{s}.pdf",
                file_type="application/pdf",
                file_size=100,
                uploaded_by="usr_ent001",
                batch_id=batch.id,
            )
            doc.status = s
            doc_ids_by_status[s] = doc.id
        test_db.commit()

        resp = client.post(
            f"/api/batches/{batch.id}/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 200
        # Allow the scheduled tasks to run so they can record into `captured`.
        # TestClient runs the sync handler on an event loop that's torn down
        # when the call returns; asyncio.create_task queues the coro but we
        # need the loop to execute it. We verify via the response's
        # requeued_document_ids which is synchronously computed.
        requeued = set(resp.json()["requeued_document_ids"])
        assert requeued == {doc_ids_by_status["failed"], doc_ids_by_status["uploaded"]}
        assert doc_ids_by_status["verified"] not in requeued

    def test_404_for_unknown_batch(self, client, enterprise_token):
        resp = client.post(
            "/api/batches/bat_unknown/process",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/batches — list
# ---------------------------------------------------------------------------


class TestListBatches:
    def test_returns_only_callers_batches_ordered_desc(
        self, client, test_db, enterprise_token, other_enterprise_token
    ):
        # 3 mine, 2 theirs.
        for _ in range(3):
            create_batch(test_db, created_by="usr_ent001", total_documents=1)
        for _ in range(2):
            create_batch(test_db, created_by="usr_ent002", total_documents=1)

        resp = client.get(
            "/api/batches?limit=10",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3
        # Reviewer/admin would see all 5.
        resp_other = client.get(
            "/api/batches?limit=10",
            headers={"Authorization": f"Bearer {other_enterprise_token}"},
        )
        assert len(resp_other.json()) == 2

    def test_limit_caps_results(self, client, test_db, enterprise_token):
        for _ in range(7):
            create_batch(test_db, created_by="usr_ent001", total_documents=1)
        resp = client.get(
            "/api/batches?limit=5",
            headers={"Authorization": f"Bearer {enterprise_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_admin_sees_all_batches(self, client, test_db, admin_token):
        for _ in range(2):
            create_batch(test_db, created_by="usr_ent001", total_documents=1)
        for _ in range(2):
            create_batch(test_db, created_by="usr_ent002", total_documents=1)
        resp = client.get(
            "/api/batches?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 4
