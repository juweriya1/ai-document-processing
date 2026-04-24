-- Batch file upload support.
--
-- Adds the `batches` table (one row per multi-file upload) and a nullable
-- `batch_id` FK on `documents`. Single-file uploads through the legacy
-- /api/documents/upload route leave `batch_id` NULL and continue to work.
--
-- Idempotent; safe to re-run. FastAPI runs the same statements on startup
-- via src/backend/main.py so this file is for humans running psql directly.

CREATE TABLE IF NOT EXISTS batches (
    id              VARCHAR PRIMARY KEY,
    created_by      VARCHAR,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    status          VARCHAR NOT NULL DEFAULT 'uploading',
    total_documents INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS batch_id VARCHAR REFERENCES batches(id);

CREATE INDEX IF NOT EXISTS ix_documents_batch_id ON documents(batch_id);
