"""Batch upload + processing routes.

Accepts N files (1..MAX) in one multipart request, creates a Batch row and N
Document rows, then fans out per-document LangGraph runs via asyncio.create_task
bounded by a module-level Semaphore. Status is polled via GET /api/batches/{id}.

Key invariants:
- Validation is all-or-nothing: if any file fails size/extension checks, the
  whole batch is rejected and nothing is written to disk or DB.
- Background tasks MUST open their own SessionLocal — the request-scoped `db`
  from Depends(get_db) closes when the handler returns.
- Re-kick (POST /{id}/process) only re-runs docs in {uploaded, failed}; this
  prevents a double-click from re-burning Gemini quota on already-processed docs.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.agents.graph import compiled_graph
from src.backend.agents.state import AgentState
from src.backend.auth.rbac import role_required
from src.backend.db.crud import (
    create_batch,
    create_document,
    get_batch,
    get_batch_with_documents,
    get_document,
    list_batches_for_user,
    update_batch_status,
)
from src.backend.db.database import SessionLocal, get_db
from src.backend.db.models import Document
from src.backend.ingestion.file_upload import FileUpload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batches", tags=["batches"])

file_uploader = FileUpload()

MAX_FILES_PER_BATCH = 20

# Concurrency bound for the in-process fan-out. PaddleOCR serializes on CPU,
# so 3 concurrent graph runs saturate the box; more just adds memory pressure.
# Env-tunable for jury demos on beefier hardware.
_BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "3"))
_batch_semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

# Status vocabulary used internally for per-document state in batch responses.
# The frontend ProcessingPage renders these via its existing status map; we
# deliberately don't translate at the API boundary here because the batch UI
# has its own badge rendering (see BatchStatusPage.js).
_TERMINAL_DOC_STATUSES = {"verified", "flagged", "failed", "approved", "rejected", "review_pending"}
_RUNNING_DOC_STATUSES = {"uploaded", "processing"}


# ---------- request/response models ----------------------------------------


class BatchDocumentSummary(BaseModel):
    id: str
    filename: str
    original_filename: str
    status: str
    fields_extracted: int = 0
    line_items_extracted: int = 0
    tier: str | None = None
    error: str | None = None


class BatchCounts(BaseModel):
    uploaded: int = 0
    processing: int = 0
    verified: int = 0
    review_pending: int = 0
    flagged: int = 0
    failed: int = 0
    approved: int = 0
    rejected: int = 0


class BatchResponse(BaseModel):
    id: str
    status: str
    created_at: str | None
    total_documents: int
    counts: BatchCounts
    documents: list[BatchDocumentSummary]


class BatchUploadResponse(BaseModel):
    batch_id: str
    document_ids: list[str]
    status: str
    total_documents: int


class BatchListItem(BaseModel):
    id: str
    status: str
    created_at: str | None
    total_documents: int


# ---------- fan-out worker -------------------------------------------------


async def _process_one(document_id: str) -> None:
    """Run the agentic graph for a single document.

    Opens its own DB session — the session from Depends(get_db) closes when
    the HTTP handler returns, so capturing it in this coroutine would be a
    use-after-close bug. Catches all exceptions so sibling docs in the batch
    continue, and sets the document to status=failed on hard failure.
    """
    async with _batch_semaphore:
        db = SessionLocal()
        batch_id: str | None = None
        try:
            doc = get_document(db, document_id)
            if doc is None:
                logger.warning("batch._process_one: document %s not found", document_id)
                return
            batch_id = doc.batch_id

            # Flip from "uploaded" → "processing" so the status poll reflects
            # in-flight work even before the graph finishes.
            doc.status = "processing"
            db.commit()

            initial = AgentState(
                document_id=document_id,
                file_path=f"uploads/{doc.filename}",
            )
            # persist_node inside the graph writes the final Document.status.
            await compiled_graph.ainvoke(initial)
        except Exception as e:
            logger.exception("batch processing failed for %s", document_id)
            try:
                doc = get_document(db, document_id)
                if doc is not None:
                    doc.status = "failed"
                    doc.rejected_reason = f"agent_execution_failed: {e}"
                    db.commit()
            except Exception:
                logger.exception("failed to record failure state for %s", document_id)
        finally:
            try:
                if batch_id:
                    _maybe_finalize_batch(db, batch_id)
            except Exception:
                logger.exception("failed to finalize batch %s", batch_id)
            db.close()


def _maybe_finalize_batch(db: Session, batch_id: str) -> None:
    """Transition Batch.status once all documents have reached a terminal state.

    - "completed":     every doc terminal AND zero failed.
    - "partial_failed": every doc terminal AND at least one failed.
    - leave as-is:     any doc still uploaded/processing.

    expire_all() forces a re-read from DB so sibling tasks that committed
    status updates on their own sessions are visible here.
    """
    db.expire_all()
    batch = get_batch(db, batch_id)
    if batch is None or batch.status in ("completed", "partial_failed"):
        return
    docs = db.query(Document).filter(Document.batch_id == batch_id).all()
    if not docs:
        return
    if any(d.status in _RUNNING_DOC_STATUSES for d in docs):
        return
    any_failed = any(d.status == "failed" for d in docs)
    batch.status = "partial_failed" if any_failed else "completed"
    db.commit()


# ---------- route handlers -------------------------------------------------


@router.post(
    "/upload",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_batch(
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    # 1. Cap-check. 1 <= N <= MAX.
    if not files:
        raise HTTPException(status_code=400, detail="batch_empty: no files provided")
    if len(files) > MAX_FILES_PER_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"batch_too_large: max {MAX_FILES_PER_BATCH} files per batch",
        )

    # 2. Read + validate ALL files first. Atomic accept/reject: nothing hits
    #    disk or DB until every file passes. Buffer contents in memory (capped
    #    at 50MB per file × 20 = 1GB worst case; acceptable for FYP scope).
    staged: list[tuple[UploadFile, bytes, str]] = []  # (upload_file, content, ext)
    for f in files:
        try:
            ext = file_uploader.validate_file_type(f.filename or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        content = await f.read()
        try:
            file_uploader.validate_file_size(content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        staged.append((f, content, ext))

    # 3. Create Batch + persist files + create Document rows in a single unit
    #    of work so that fan-out tasks can always find their doc by id.
    batch = create_batch(
        db,
        created_by=current_user.get("user_id"),
        total_documents=len(staged),
        status="processing",
    )

    document_ids: list[str] = []
    for f, content, ext in staged:
        stored_filename = file_uploader.get_stored_filename(ext)
        file_path = os.path.join(file_uploader.upload_dir, stored_filename)
        with open(file_path, "wb") as fh:
            fh.write(content)
        doc = create_document(
            db,
            filename=stored_filename,
            original_filename=f.filename or stored_filename,
            file_type=f.content_type or "application/octet-stream",
            file_size=len(content),
            uploaded_by=current_user.get("user_id"),
            batch_id=batch.id,
        )
        document_ids.append(doc.id)

    # 4. Fan out. create_task schedules on the running loop; tasks outlive
    #    this request. Background tasks own their sessions (see _process_one).
    for doc_id in document_ids:
        asyncio.create_task(_process_one(doc_id))

    return BatchUploadResponse(
        batch_id=batch.id,
        document_ids=document_ids,
        status=batch.status,
        total_documents=batch.total_documents,
    )


@router.get("/{batch_id}", response_model=BatchResponse)
def get_batch_status(
    batch_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    batch = get_batch_with_documents(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    # Owner gate — enterprise_user only sees their own batches; admin/reviewer see all.
    role = current_user.get("role")
    if role == "enterprise_user" and batch.created_by != current_user.get("user_id"):
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    counts = BatchCounts()
    docs_out: list[BatchDocumentSummary] = []
    for doc in batch.documents:
        _increment_counts(counts, doc.status)
        docs_out.append(BatchDocumentSummary(
            id=doc.id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            status=doc.status,
            fields_extracted=_count_fields(doc),
            line_items_extracted=_count_line_items(doc),
            tier=doc.fallback_tier,
            error=doc.rejected_reason,
        ))

    return BatchResponse(
        id=batch.id,
        status=batch.status,
        created_at=batch.created_at.isoformat() if batch.created_at else None,
        total_documents=batch.total_documents,
        counts=counts,
        documents=docs_out,
    )


@router.post("/{batch_id}/process")
async def reprocess_batch(
    batch_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    """Idempotent re-kick — only re-runs docs in {uploaded, failed}.

    Protects Gemini quota: re-clicking the button will not re-run already-
    verified or in-flight documents.
    """
    batch = get_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    role = current_user.get("role")
    if role == "enterprise_user" and batch.created_by != current_user.get("user_id"):
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    to_run = (
        db.query(Document)
        .filter(Document.batch_id == batch_id)
        .filter(Document.status.in_(["uploaded", "failed"]))
        .all()
    )
    to_run_ids = [d.id for d in to_run]

    if to_run_ids:
        update_batch_status(db, batch_id, "processing")
        for doc_id in to_run_ids:
            asyncio.create_task(_process_one(doc_id))

    return {
        "batch_id": batch_id,
        "requeued_document_ids": to_run_ids,
        "status": "processing" if to_run_ids else batch.status,
    }


@router.get("", response_model=list[BatchListItem])
def list_batches(
    limit: int = Query(default=5, ge=1, le=50),
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    role = current_user.get("role")
    include_all = role in ("admin", "reviewer")
    batches = list_batches_for_user(
        db,
        user_id=current_user.get("user_id"),
        limit=limit,
        include_all=include_all,
    )
    return [
        BatchListItem(
            id=b.id,
            status=b.status,
            created_at=b.created_at.isoformat() if b.created_at else None,
            total_documents=b.total_documents,
        )
        for b in batches
    ]


# ---------- helpers --------------------------------------------------------


def _increment_counts(counts: BatchCounts, doc_status: str) -> None:
    mapping = {
        "uploaded": "uploaded",
        "processing": "processing",
        "verified": "verified",
        "review_pending": "review_pending",
        "flagged": "flagged",
        "failed": "failed",
        "approved": "approved",
        "rejected": "rejected",
    }
    key = mapping.get(doc_status)
    if key is None:
        return
    setattr(counts, key, getattr(counts, key) + 1)


def _count_fields(doc: Document) -> int:
    """Count non-empty extracted fields — avoids a separate query per row when
    the relationship is already eager-loaded."""
    try:
        return sum(1 for f in doc.extracted_fields if f.field_value)
    except Exception:
        return 0


def _count_line_items(doc: Document) -> int:
    try:
        return len(doc.line_items)
    except Exception:
        return 0
