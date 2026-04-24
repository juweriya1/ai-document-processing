-- Agentic Financial Auditor — add columns the pipeline has been writing to
-- since document_processor.py was introduced but that were never declared on
-- the Document model. Idempotent; safe to run repeatedly.
--
-- Run once against the local Postgres (port 5433 per CLAUDE.md):
--   psql "postgresql://localhost:5433/idp" -f scripts/migrations/add_traceability_columns.sql

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS traceability_log JSONB;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS fallback_tier VARCHAR(32);

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION;

-- Index the tier column for dashboards that filter by local-vs-vlm-vs-hitl.
CREATE INDEX IF NOT EXISTS idx_documents_fallback_tier
    ON documents (fallback_tier);
