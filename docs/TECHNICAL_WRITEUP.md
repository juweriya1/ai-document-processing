# AI Document Processing Platform — Technical Write-Up

## 1. Project Overview

An enterprise-grade **Intelligent Document Processing (IDP) platform** for financial documents (primarily invoices). Its goal is **Straight-Through Processing (STP)** — extracting structured data automatically with enough accuracy and auditability to minimize human intervention, while catching every case where the model is unreliable.

The design follows a **"Dual-Brain" philosophy**: *fast by default, intelligent by exception*. A deterministic local pipeline handles the common path in under a second; a multimodal LLM is invoked only when that pipeline fails a numeric audit.

---

## 2. High-Level Architecture

```
Upload → Preprocess → Tier 1 (PaddleOCR + Heuristics)
                           ↓
                   Financial Auditor (Decimal math + Magnitude Guard)
                     ↓ fail         ↓ pass
              Tier 2 (Gemini via BAML)     Persist + Verified
                     ↓
                 Auditor (loop ≤3)
                     ↓ unresolved
                  HITL Review
```

The pipeline is a **LangGraph `StateGraph`** (`src/backend/agents/graph.py`) with five nodes — `preprocess`, `ocr`, `auditor`, `reconciler`, `persist` — and two conditional routers. Every transition is recorded in a JSONB `traceability_log`.

---

## 3. Technology Stack

### Backend (Python 3.11, FastAPI)

| Concern | Library |
|---|---|
| Web framework | `fastapi==0.115.6`, `uvicorn==0.34.0` |
| ORM / DB | `sqlalchemy==2.0.36`, `psycopg2-binary==2.9.10` (PostgreSQL 15 on port 5433) |
| Auth | `python-jose`, `passlib[bcrypt]`, `bcrypt==4.0.1` — JWT + RBAC |
| OCR (Tier 1) | `paddleocr>=3.5.0` (PP-OCRv5, CPU mobile detection + recognition) |
| Image / PDF | `opencv-python-headless`, `Pillow`, `pdf2image`, `pdfplumber` |
| Agentic orchestration | `langgraph>=1.1.0` |
| LLM contracts | `baml-py==0.221.0` — type-safe Gemini schemas |
| LLM SDK | `google-genai>=0.8.0` (Gemini 2.5 Flash + Flash-Lite fallback) |
| Analytics | `pandas`, `scikit-learn==1.8.0`, `statsmodels` |
| Testing | `pytest==8.3.4` |

### Frontend (React 19)

- `react==19.2.4`, `react-dom==19.2.4`
- `react-router-dom==7.13.0`
- `react-scripts==5.0.1` (CRA)
- Plain CSS with variables (teal primary), BEM-lite naming — no CSS framework
- JWT + React Context auth, auto-logout on 401
- Dev proxy → `http://localhost:8000`

### Infrastructure

- PostgreSQL 15 (port 5433)
- Tier 1 is CPU-local; Tier 2 is serverless Gemini — the system scales horizontally

---

## 4. AI Stack

### Tier 1 — High-Speed Local Extractor (`extraction/local_extractor.py`)

- **PaddleOCR** (PP-OCRv5 mobile, CPU) produces text + bounding boxes
- `extraction/heuristics.py` applies **regex + spatial heuristics**: label-to-value matching via bounding-box proximity, amount triangulation (subtotal + tax ≈ total), currency parsing for `$ / € / £` with standard Western thousands-separator grouping
- The OCR engine is cached at the class level (`_shared_engine`) to amortize initialization cost, with a thread lock (`_predict_lock`) that serializes forward passes while allowing pre/post-processing concurrency
- Target latency: **<800ms** per document
- Raises `LocalExtractorUnavailable` on failure → graph escalates to Tier 2

### Tier 2 — Agentic Reconciler (`extraction/neural_fallback.py` + `baml_src/`)

- **Gemini 2.5 Flash** (primary) with **Gemini 2.5 Flash-Lite** fallback, retry policy 3× exponential backoff (500ms → 8s)
- All interactions are defined as **BAML contracts** (`baml_src/extraction.baml`):
  - `ExtractInvoice(image) -> InvoiceExtraction`
  - `ReconcileInvoice(image, error_context) -> InvoiceExtraction`
- The reconciler receives **raw image bytes plus targeted error context** (e.g., *"Audit failed: Total is off by 990.00. Check for misplaced decimal points."*). This is the key to the self-correcting loop — the LLM is told *what went wrong* and re-reads the image, not just the OCR text
- BAML generates a typed Python client (`baml_client/`), so the LLM output is validated against the `InvoiceExtraction` schema before reaching the auditor

### Why this split

- Deterministic code is cheap, traceable, and fast — use it for the easy path
- LLMs are slow, expensive, and non-deterministic — invoke them only when the auditor has *proven* something is wrong, so every LLM call has a concrete remediation target

---

## 5. The Financial Auditor (`validation/auditor.py`)

The auditor is the **control center** of the pipeline — it decides whether Tier 1 output is trustworthy.

- **Zero Float Tolerance.** All amounts become `decimal.Decimal` before math
- **Tolerance:** `Decimal("0.01")` for mismatch between sum(line items) + tax and total
- **Magnitude Guard** — the headline novelty. If a straight audit fails, the auditor tests ratios `10, 100, 0.1, 0.01` between `sum(items)` and `total`. If any ratio lands within ±5%, it flags a `SCALE_ERROR` (a "Decimal Slip" — e.g., "1000" read as "10.00"). Guidance sent to the reconciler explicitly instructs *"check for misplaced decimals"*
- Returns an `AuditResult` with `is_valid`, failed field list, and structured reason codes (`pipeline/reason_codes.py`)

---

## 6. Agent Orchestration (`src/backend/agents/`)

`graph.py` defines the state machine; `nodes.py` implements each step; `state.py` holds the Pydantic `AgentState`.

**Routing rules:**

| Router | Condition | Target |
|---|---|---|
| `_route_after_preprocess` | `state.pages` set | `ocr` |
| | preprocess failed | `persist` (HITL) |
| `_route_after_auditor` | `state.is_valid` | `persist` (verified) |
| | `attempts >= 3` or `tier == "hitl"` | `persist` (flagged) |
| | otherwise | `reconciler` |
| Post-reconciler | unconditional | `auditor` (loop) |

**Key constants:**
- `LOCAL_CONFIDENCE_THRESHOLD = 0.85` — passing audit is still escalated if PaddleOCR confidence is below this
- `MAX_RECONCILE_ATTEMPTS = 3` — bounded to prevent infinite LLM loops

Every node appends a `TraceEntry` to `documents.traceability_log`.

---

## 7. HITL Policy & Risk-Aware Routing (`pipeline/hitl_policy.py`)

Not every field is equally important. The policy assigns **criticality weights** (e.g., `total_amount` > `vendor_name` > `date`) and computes an **effective threshold** per field that blends:

- Base confidence score
- Field criticality
- Historical correction rate (via `pipeline/confidence_calibrator.py`, which learns per-field thresholds from the `corrections` table)

`GET /api/documents/{id}/fields?hitl=true` returns only fields that exceed the effective threshold's risk budget — so reviewers see the *actually risky* fields, not a 30-field checklist.

---

## 8. Data Layer (`db/models.py`)

| Table | Key columns |
|---|---|
| `users` | role (`enterprise_user` / `reviewer` / `admin`), `is_active` |
| `documents` | `status`, `traceability_log` (JSONB), `fallback_tier`, `confidence_score`, `batch_id`, `approved_by`, `rejected_reason` |
| `batches` | `status`, `total_documents` |
| `extracted_fields` | `field_name`, `field_value`, `confidence`, `status`, `error_message` |
| `line_items` | `sequence`, `description`, `quantity`, `unit_price`, `total` |
| `corrections` | `original_value`, `corrected_value`, `reviewer_id` — feeds calibrator |

Document status flow: `uploaded → preprocessing → extracting → validating → review_pending → approved / rejected`.

---

## 9. API Surface

- **Auth** — `POST /api/auth/{login,register}`
- **Upload** — `POST /api/documents/upload` (single), `POST /api/batches` (up to 20 files, all-or-nothing validation)
- **Agentic pipeline** — `POST /api/agentic/{id}/process` (async, LangGraph), `GET /api/agentic/{id}/status`
- **Validation & HITL** — `GET/POST /api/documents/{id}/fields`, `/corrections`, `/approve`, `/reject`
- **Batch** — `GET /api/batches/{id}`, `POST /api/batches/{id}/process` (fan-out with `Semaphore(3)` concurrency bound)
- **Analytics** — `/api/analytics/{dashboard, spend/by-vendor, spend/by-month, suppliers, predictions, anomalies}`
- **Admin** — `/api/admin/users` CRUD, role management

All routes use FastAPI dependency injection for DB session + JWT + `role_required(...)` RBAC checks.

---

## 10. Frontend Pages (`frontend/src/pages/`)

| Page | Role |
|---|---|
| Login | JWT auth, register |
| Dashboard | Document list, batch history, quick stats |
| Upload / BatchUpload | Single-file drag-drop / multi-file batch |
| Processing / BatchStatus | Poll agentic endpoint, stepper UI |
| Validation | Field-by-field confidence + risk display, correction submission |
| Review | HITL review with image overlay showing *what the agent saw vs. corrected* |
| Insights | Spend trends, supplier analysis, anomalies |
| Admin | User CRUD, role assignment |

---

## 11. Analytics (`src/backend/analytics/`)

Six modules, all with graceful degradation when data is thin:

| Module | Model | Fallback |
|---|---|---|
| `risk_scorer.py` | Random Forest | Heuristic weighting if <5 suppliers |
| `trend_forecaster.py` | ARIMA | Linear regression if <6 months |
| `anomaly_detector.py` | Isolation Forest | Z-score if <10 documents |
| `aggregator.py` / `supplier_analyzer.py` / `insights_generator.py` | pandas aggregations | — |

---

## 12. Evaluation & Testing

**Unit tests** (`tests/unit/`) cover the active pipeline:
- Agent graph nodes, routing, retry bounds
- Auditor Decimal logic + Magnitude Guard edge cases
- Local extractor + heuristics
- Neural fallback (mocked Gemini)
- Route-level tests for agentic pipeline, validation, batch, RBAC
- Analytics (anomalies, trends, aggregation)
- Confidence calibrator

**Integration tests** (`tests/integration/`):
- `test_pipeline_end_to_end.py` — full LangGraph run with real DB
- `test_validation_hitl_flow.py` — HITL routing + correction workflow
- `test_rbac_flow.py` — auth + role enforcement end-to-end
- `test_analytics_flow.py` — analytics aggregation

**Smoke / benchmark scripts** (`scripts/`):
- `smoke_tier1.py` — Tier-1 only (no Gemini)
- `smoke_agentic.py` — real document from DB, prints full trace
- `smoke_agentic_vlm.py` — force Tier-2 reconciler path
- `smoke_http.sh` — curl-based endpoint smoke
- `bench_ocr_parallel.py` — sequential vs. concurrent OCR + simulated Gemini I/O, demonstrates `asyncio.to_thread` event-loop responsiveness and `Semaphore(3)` batch concurrency

---

## 13. Design Principles

1. **Contract-Driven Development** — every LLM boundary is typed via BAML schemas; no free-form JSON parsing
2. **Zero Float Tolerance** — all financial math uses `decimal.Decimal`
3. **Full Traceability** — every node writes to `traceability_log`; reviewers can reconstruct why a document was flagged
4. **Fail-safe escalation** — if any tier fails (preprocess error, Paddle OOM, Gemini quota), the graph routes to HITL rather than silently dropping the document
5. **Bounded recursion** — max 3 reconciler loops prevents LLM hallucination spirals and cost runaway
6. **Horizontal scalability** — Tier 1 is CPU-local, Tier 2 is serverless; batch fan-out uses a bounded Semaphore so a large batch can't starve other users
7. **Feedback loop** — the `corrections` table feeds the confidence calibrator, so HITL thresholds get more precise over time

---

## 14. Summary

Three concentric layers:

- **Deterministic core** (PaddleOCR + regex/spatial heuristics + Decimal auditor) — handles the fast path and provides the ground truth for "is this output correct?"
- **Agentic correction layer** (LangGraph + BAML + Gemini 2.5 Flash) — invoked *only* when the deterministic core proves something is wrong, given targeted remediation context
- **Human layer** (HITL Review UI + correction feedback) — the final safety net, with risk-aware routing that surfaces only fields that genuinely need human judgment

Novel contributions: (a) the **Magnitude Guard** for decimal-slip detection, (b) **typed LLM contracts via BAML** eliminating a whole class of parse-error failures, and (c) **full JSONB traceability** of every agent decision for regulatory auditability.
