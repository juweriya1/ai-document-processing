import asyncio
import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.backend.api.routes_admin import router as admin_router
from src.backend.api.routes_agentic import router as agentic_router
from src.backend.api.routes_analytics import router as analytics_router
from src.backend.api.routes_auth import router as auth_router
from src.backend.api.routes_batch import router as batch_router
from src.backend.api.routes_pipeline import router as pipeline_router
from src.backend.api.routes_upload import router as upload_router
from src.backend.api.routes_validation import router as validation_router
from src.backend.db.database import engine
from src.backend.db.models import Base

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDP Platform", version="0.1.0")


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "is_active BOOLEAN NOT NULL DEFAULT true"
        ))
        # Agentic pipeline columns — populated by the LangGraph persist_node
        # and by the legacy DocumentProcessor. Idempotent ALTER TABLEs keep
        # existing DBs in sync without requiring a full migration framework.
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS traceability_log JSONB"))
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS fallback_tier VARCHAR(32)"))
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION"))
        # Batch upload support — Batch table + FK on documents. Idempotent so
        # existing DBs in sync without requiring a full migration framework.
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS batches (
                id              VARCHAR PRIMARY KEY,
                created_by      VARCHAR,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                status          VARCHAR NOT NULL DEFAULT 'uploading',
                total_documents INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS batch_id VARCHAR REFERENCES batches(id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_documents_batch_id ON documents(batch_id)"
        ))
        conn.commit()


def _warm_paddleocr() -> None:
    """Force PaddleOCR to load its detection + recognition models into RAM.

    Runs in a worker thread from the startup hook. The first user request
    then only pays the inference cost (~1-4s on M-series CPU with mobile_det)
    instead of the 90-120s cold-model-load. Opt-in via `WARMUP_MODELS=1` so
    local dev and the test suite don't eat the startup cost.
    """
    try:
        import numpy as np
        from src.backend.extraction.local_extractor import LocalExtractor
        t0 = time.perf_counter()
        ext = LocalExtractor()
        ext._load()  # loads det + rec weights
        # A 64x64 dummy page triggers one forward pass so the allocator, thread
        # pool and any lazy-compiled ops are warmed beyond just file-to-RAM.
        dummy_page = type("Page", (), {
            "processed": np.full((64, 64, 3), 255, dtype=np.uint8),
            "original": None,
        })()
        try:
            import asyncio
            asyncio.run(ext.extract([dummy_page]))
        except Exception:
            pass  # first inference can warn; we only care that weights are resident
        logger.info("paddleocr warmup complete in %.1fs", time.perf_counter() - t0)
    except Exception as e:
        logger.warning("paddleocr warmup skipped: %s", e)


@app.on_event("startup")
async def warm_models_if_requested():
    if os.getenv("WARMUP_MODELS") != "1":
        return
    # Offload to a thread so the HTTP server reports "ready" immediately; the
    # first real request will wait on the thread if it hasn't finished.
    asyncio.create_task(asyncio.to_thread(_warm_paddleocr))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(batch_router)
app.include_router(validation_router)
app.include_router(pipeline_router)
app.include_router(agentic_router)
app.include_router(analytics_router)
app.include_router(admin_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
