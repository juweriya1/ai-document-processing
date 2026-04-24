#!/usr/bin/env bash

set -e

REPO="juweriya1/ai-document-processing"

create() {
  title="$1"
  body="$2"
  labels="$3"

  echo "Creating: $title"

  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --body "$body" \
    --label "$labels"
}

# ----------------------------
# CORE PIPELINE
# ----------------------------

create "Issue #1 — Define DocState enum and state-machine skeleton" \
"Create DocState enum matching DB status fields and enforce valid transitions.

- Define RECEIVED, PREPROCESSED, LOCALLY_PARSED, VLM_RECONCILED, VERIFIED, FLAGGED, FAILED
- Add transition guard helper
- Map directly to Document.status

AC: invalid transitions raise error; unit test covers valid + invalid flows" \
"backend,pipeline,priority:high"

create "Issue #2 — DocumentProcessor async state machine" \
"Replace current orchestrator with async pipeline:

- RECEIVED → VERIFIED/FLAGGED flow
- Tier 1 local extraction
- Tier 2 VLM fallback
- Trace logging at each step

Must be fully async and isolated per tier." \
"backend,pipeline,priority:high"

create "Issue #3 — Mid-pipeline persistence checkpoints" \
"Persist state after every transition.

- DB write at each stage boundary
- Recovery-safe traceability_log updates
- No in-memory-only state transitions" \
"backend,pipeline,priority:high"

create "Issue #4 — Standardized failure reason codes" \
"Introduce ReasonCode enum.

Replace all free-text errors with structured codes:
LOCAL_IMPORT_ERROR, AUDIT_MATH_MISMATCH, VLM_API_ERROR, etc.

Must be used across pipeline and extraction layers." \
"backend,observability"

create "Issue #5 — Module bypass on Tier-1 failure" \
"Local extractor must never crash pipeline.

- ImportError or runtime error → fallback to Tier 2
- Log reason code
- Continue execution" \
"backend,pipeline,priority:high"

create "Issue #6 — Tier-2 retry logic (max 1 retry)" \
"Add retry wrapper for Gemini calls.

- Retry only once
- Only for transient errors
- Permanent failures go to FLAGGED" \
"backend,pipeline,priority:high"

create "Issue #7 — PipelineOrchestrator compatibility shim" \
"Keep existing orchestrator API.

- Delegate to new DocumentProcessor
- Remove legacy logic
- Maintain backward compatibility" \
"backend,tech-debt"

# ----------------------------
# EXTRACTION
# ----------------------------

create "Issue #8 — LocalExtractor scaffold (PaddleOCR lazy load)" \
"Create Tier-1 extractor wrapper with lazy import.

- No heavy imports at module load
- Graceful unavailable state" \
"backend,extraction"

create "Issue #9 — OCR heuristics layer for field extraction" \
"Convert raw OCR text into structured invoice fields.

- invoice number, date, vendor, totals
- regex + heuristics only" \
"backend,extraction"

create "Issue #10 — Map OCR output to ExtractedField schema" \
"Convert heuristics output into DB-ready schema.

- match store_extracted_fields format
- safe empty handling" \
"backend,extraction"

create "Issue #11 — NeuralFallback (BAML + Gemini)" \
"Tier-2 extraction wrapper.

- BAML client integration
- fallback error mapping
- unified output format with Tier-1" \
"backend,extraction,priority:high"

create "Issue #12 — Direct Gemini fallback without BAML" \
"If BAML unavailable, fallback to google-genai directly.

- same output schema
- shared prompt logic" \
"backend,extraction"

create "Issue #13 — Cropped region extraction for VLM input" \
"Crop invoice regions before sending to VLM.

- totals area
- line item table area
- fallback heuristic crop if detection fails" \
"backend,extraction"

create "Issue #14 — Empty extraction detector" \
"Detect useless OCR output.

- empty fields
- missing key invoice fields
- force Tier-2 escalation" \
"backend,extraction"

create "Issue #15 — Confidence scoring redesign" \
"Replace OCR confidence with composite score:

- field completeness
- audit pass/fail
- heuristic strength
- OCR confidence (minor weight)" \
"backend,validation"

# ----------------------------
# VALIDATION / CURRENCY / AUDIT
# ----------------------------

create "Issue #16 — Currency parser (PKR + lakh support)" \
"Parse messy currency formats:

- Rs. 5,000/-
- 1,50,000
- $2,450
- return Decimal safely" \
"backend,validation"

create "Issue #17 — FinancialAuditor engine" \
"Validate invoice math:

subtotal + tax == total

Return structured audit report with delta." \
"backend,validation"

create "Issue #18 — Partial-data audit policy" \
"Define behavior when subtotal/tax missing.

- do not crash
- mark partial audit state
- route based on tier" \
"backend,validation"

# ----------------------------
# TESTING
# ----------------------------

create "Issue #19 — Currency parser tests" \
"Unit tests for all currency formats including PK styles." \
"testing"

create "Issue #20 — Auditor tests" \
"Test math pass, fail, partial data, malformed inputs." \
"testing"

# ----------------------------
# DATABASE
# ----------------------------

create "Issue #21 — Add traceability columns to Document model" \
"Add:

- traceability_log
- confidence_score
- fallback_tier" \
"backend,db"

create "Issue #22 — Startup DB migrations (ALTER TABLE)" \
"Add safe startup migrations for new columns." \
"backend,db"

create "Issue #23 — Checkpoint persistence helper" \
"DB helper to persist state + trace per transition." \
"backend,db"

# ----------------------------
# API
# ----------------------------

create "Issue #24 — BackgroundTasks pipeline execution" \
"Make /process async using FastAPI BackgroundTasks." \
"backend,api"

create "Issue #25 — Extend /status with trace + tier info" \
"Expose traceability_log, confidence_score, fallback_tier." \
"backend,api"

create "Issue #26 — Isolated DB session for worker" \
"Worker must not reuse request session." \
"backend,api"

# ----------------------------
# OBSERVABILITY
# ----------------------------

create "Issue #27 — TraceEntry dataclass" \
"Structured trace logging for pipeline stages." \
"backend,observability"

create "Issue #28 — Structured logging for pipeline events" \
"Emit JSON logs per state transition." \
"backend,observability"

create "Issue #29 — ReasonCode documentation" \
"Document all failure codes and meanings." \
"backend,observability"

# ----------------------------
# TESTING (INTEGRATION)
# ----------------------------

create "Issue #30 — Happy path integration test" \
"Local success → VERIFIED pipeline test." \
"testing"

create "Issue #31 — Fallback behavior tests" \
"Local fail → VLM success/fail scenarios." \
"testing"

create "Issue #32 — Empty extraction integration test" \
"Ensure empty OCR triggers fallback." \
"testing"

create "Issue #33 — VLM retry behavior test" \
"Ensure retry logic works exactly once." \
"testing"

create "Issue #34 — End-to-end real invoice test" \
"Run full pipeline with real PDF sample." \
"testing"

# ----------------------------
# DEVOPS
# ----------------------------

create "Issue #35 — Add dependencies (BAML, PaddleOCR, Gemini SDK)" \
"Update requirements.txt with all new deps." \
"infra"

create "Issue #36 — Config env variables setup" \
"Add GOOGLE_API_KEY and thresholds." \
"infra"

create "Issue #37 — BAML source definitions" \
"Define invoice extraction schema and client." \
"extraction"

create "Issue #38 — Generate and commit baml_client" \
"Run baml-cli generate and commit output." \
"infra"

create "Issue #39 — .env.example update" \
"Add missing environment variables template." \
"infra"
