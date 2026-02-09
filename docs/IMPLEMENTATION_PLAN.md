# Implementation Plan — IDP Platform

## Phase Overview

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Foundation | **Done** | Project skeleton, database, auth, file upload, preprocessing |
| 2 | Core AI | Planned | OCR, layout analysis, table extraction, NER, field mapping |
| 3 | Validation & HITL | Planned | Schema validation, correction workflow, pipeline orchestrator |
| 4 | Analytics | Planned | Dashboard metrics, predictions, anomaly detection |
| 5 | Frontend | Planned | React.js UI — all 8 pages connected to backend APIs |
| 6 | Integration Testing | Planned | End-to-end pipeline tests, BDD scenarios |

---

## Phase 1 — Foundation (Done)

### What Was Built

Six feature branches were merged to `main`, each following the TDD workflow (write tests first, then implement, then verify).

#### Step 1.1: Project Skeleton (`feature/project-setup`)

| Deliverable | Detail |
|-------------|--------|
| FastAPI app | `src/backend/main.py` — CORS middleware, `GET /health` endpoint |
| Config | `src/backend/config.py` — env vars with defaults for DB, JWT, uploads |
| Package structure | 6 `__init__.py` files creating `src.backend.{api,auth,db,ingestion}` |
| Dependencies | `src/backend/requirements.txt` — 15 pinned packages |
| Test scaffold | `tests/conftest.py`, `tests/unit/__init__.py` |
| Git config | `.gitignore`, `.env.example`, `pyproject.toml` (pytest paths) |
| Upload dir | `uploads/.gitkeep` |

#### Step 1.2: Database Layer (`feature/database-setup`)

| Deliverable | Detail |
|-------------|--------|
| Connection | `src/backend/db/database.py` — engine, SessionLocal, `get_db()` dependency |
| Models | `src/backend/db/models.py` — 7 ORM models (User, Document, ExtractedField, LineItem, Correction, AnalyticsSummary, SupplierMetric) |
| CRUD | `src/backend/db/crud.py` — create/get document, store fields, create/get user, verify password |
| Tests | `tests/unit/test_database_crud.py` — 6 tests |
| Fixtures | `tests/conftest.py` — db_engine, db_session, sample_document |

**Endpoint-to-module mapping**: No new endpoints. Database is consumed by auth and upload routes.

#### Step 1.3: Authentication (`feature/auth`)

| Deliverable | Detail |
|-------------|--------|
| JWT | `src/backend/auth/jwt_handler.py` — create_access_token, verify_token, get_current_user |
| RBAC | `src/backend/auth/rbac.py` — require_role (unit-testable), role_required (FastAPI dependency) |
| Routes | `src/backend/api/routes_auth.py` — `POST /api/auth/register`, `POST /api/auth/login` |
| Tests | `tests/unit/test_jwt_handler.py` — 4 tests; `tests/unit/test_rbac.py` — 4 tests |

**Endpoint-to-module mapping**:

| Endpoint | Module | CRUD Function |
|----------|--------|---------------|
| `POST /api/auth/register` | routes_auth → crud | `create_user()` |
| `POST /api/auth/login` | routes_auth → crud, jwt_handler | `get_user_by_email()`, `verify_password()`, `create_access_token()` |

#### Step 1.4: File Upload (`feature/file-upload`)

| Deliverable | Detail |
|-------------|--------|
| Upload handler | `src/backend/ingestion/file_upload.py` — FileUpload class, DocumentMeta dataclass |
| Route | `src/backend/api/routes_upload.py` — `POST /api/documents/upload` |
| Tests | `tests/unit/test_file_upload.py` — 7 tests |

**Endpoint-to-module mapping**:

| Endpoint | Module | Auth | CRUD Function |
|----------|--------|------|---------------|
| `POST /api/documents/upload` | routes_upload → file_upload, crud | `role_required(["enterprise_user", "admin", "reviewer"])` | `create_document()` |

#### Step 1.5: Preprocessing (`feature/preprocessing`)

| Deliverable | Detail |
|-------------|--------|
| Preprocessor | `src/backend/ingestion/preprocessing.py` — Preprocessing class, PreprocessedPage dataclass |
| Test fixture | `tests/fixtures/sample_invoice.pdf` — 1-page synthetic invoice |
| Tests | `tests/unit/test_preprocessing.py` — 5 tests |

**Endpoint-to-module mapping**: No endpoint. The Preprocessing class is a library consumed by the pipeline orchestrator (Phase 3). It is fully tested and functional but not yet exposed via any API route.

#### Step 1.6: Integration Verification (`feature/phase1-integration`)

| Deliverable | Detail |
|-------------|--------|
| Startup fix | `main.py` — added `@app.on_event("startup")` to auto-create DB tables |
| Upload fix | `file_upload.py` — handle FastAPI UploadFile's `file.file.read()` for sync access |
| Verification | Full test suite (26 pass), smoke test (health → register → login → upload) |

### Production-Ready vs Placeholder

| Component | Status | Notes |
|-----------|--------|-------|
| `GET /health` | Production-ready | Stateless check, no dependencies |
| `POST /api/auth/register` | Production-ready | Creates user with bcrypt hash, checks duplicate email |
| `POST /api/auth/login` | Production-ready | Verifies credentials, returns JWT |
| `POST /api/documents/upload` | Production-ready | Validates type/size, stores file, creates DB record, requires auth |
| JWT token system | Production-ready (dev keys) | Functional but uses dev SECRET_KEY — must change for production |
| RBAC enforcement | Production-ready | Three roles enforced on upload route |
| Database schema | Production-ready | 7 models with relationships, auto-created on startup |
| CRUD operations | Partially complete | Document and User CRUD done; LineItem, Correction, Analytics CRUD not yet written |
| Preprocessing pipeline | Tested, not wired | `Preprocessing` class works but no API endpoint invokes it yet |
| ORM models: LineItem, Correction, AnalyticsSummary, SupplierMetric | Schema only | Tables exist; no CRUD functions, no routes, no business logic |
| CORS policy | Dev only | Currently allows all origins — must restrict for production |

---

## Phase 2 — Core AI (Planned)

### Objective
Add OCR, layout analysis, and NLP extraction so that uploaded documents produce structured data.

### Planned Modules

| Module | Package | Libraries | Purpose |
|--------|---------|-----------|---------|
| OCR Engine | `src/backend/ocr/` | Tesseract (primary), EasyOCR (fallback), PaddleOCR | Extract raw text from preprocessed images |
| Layout Analyzer | `src/backend/layout_engine/` | LayoutParser + Detectron2 | Detect regions (headers, tables, paragraphs, key-value pairs) |
| Table Extractor | `src/backend/extraction/` | pdfplumber, custom logic | Extract structured table data into LineItem records |
| NLP Extractor | `src/backend/extraction/` | spaCy NER + HuggingFace Transformers + regex | Extract named fields (invoice number, date, amounts, vendor) |
| Field Mapper | `src/backend/extraction/` | Custom | Map extracted entities to ExtractedField records with confidence scores |

### Planned Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/documents/{id}/process` | Trigger OCR + extraction pipeline on an uploaded document |
| `GET /api/documents/{id}/results` | Retrieve extracted fields and line items for a document |

### Prerequisites
- Phase 1 complete (done)
- Tesseract installed (`brew install tesseract`)
- Detectron2 compatible with Python 3.11 / ARM64

---

## Phase 3 — Validation & HITL (Planned)

### Objective
Add schema-based validation of extracted fields and a human-in-the-loop correction workflow.

### Planned Modules

| Module | Package | Purpose |
|--------|---------|---------|
| Schema Validator | `src/backend/validation/` | Validate extracted fields against expected schemas (field types, ranges, required fields) |
| Correction Handler | `src/backend/validation/` | Accept human corrections, store in Correction table, update ExtractedField values |
| Pipeline Orchestrator | `src/backend/pipeline/` | Chain: upload → preprocess → OCR → extract → validate → [HITL] → store |

### Planned Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/documents/{id}/validation` | Get validation status and errors for a document |
| `POST /api/documents/{id}/corrections` | Submit human corrections for specific fields |
| `GET /api/documents/{id}/review` | Get document data formatted for HITL review interface |

### Prerequisites
- Phase 2 complete (OCR and extraction producing data to validate)

---

## Phase 4 — Analytics (Planned)

### Objective
Build dashboard metrics, predictive models, and anomaly detection.

### Planned Modules

| Module | Package | Libraries | Purpose |
|--------|---------|-----------|---------|
| Dashboard Metrics | `src/backend/analytics/` | Plotly | Processing volume, accuracy trends, document type distribution |
| Predictions | `src/backend/analytics/` | scikit-learn (Random Forest), statsmodels (ARIMA/Prophet) | Risk scoring, trend forecasting |
| Anomaly Detection | `src/backend/analytics/` | scikit-learn (Isolation Forest) | Flag unusual documents or extraction patterns |
| Supplier Analytics | `src/backend/analytics/` | Custom | Per-supplier metrics using SupplierMetric table |

### Planned Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/analytics/dashboard` | Aggregated metrics for dashboard display |
| `GET /api/analytics/predictions` | Trend predictions and risk scores |
| `GET /api/analytics/suppliers` | Per-supplier performance metrics |

### Prerequisites
- Phase 3 complete (enough processed documents with validated data to analyze)

---

## Phase 5 — Frontend (Planned)

### Objective
Build 8 React.js pages connected to the backend API.

### Planned Pages

| Page | Route | Backend Endpoints Used |
|------|-------|----------------------|
| Login | `/login` | `POST /api/auth/login` |
| Dashboard | `/dashboard` | `GET /api/analytics/dashboard` |
| Upload | `/upload` | `POST /api/documents/upload` |
| Processing | `/processing` | `GET /api/documents/{id}/results` |
| Validation | `/validation` | `GET /api/documents/{id}/validation` |
| HITL Review | `/review` | `GET /api/documents/{id}/review`, `POST /api/documents/{id}/corrections` |
| Insights | `/insights` | `GET /api/analytics/predictions`, `GET /api/analytics/suppliers` |
| Admin | `/admin` | User management endpoints (not yet defined) |

### Prerequisites
- Backend APIs for all consumed endpoints must be functional
- UI wireframes from the UI/UX team (currently using SRS wireframes as fallback)

---

## Phase 6 — Integration Testing (Planned)

### Objective
End-to-end tests covering the full pipeline from upload through analytics.

### Planned Test Scenarios (BDD)

1. Upload a PDF → verify preprocessing images are generated
2. Upload → process → verify OCR text is extracted
3. Upload → process → verify NER fields are mapped to ExtractedField records
4. Upload → process → validate → verify validation errors are reported
5. Upload → process → validate → correct → verify Correction records are stored
6. Process multiple documents → verify analytics summaries are computed

### Prerequisites
- All previous phases functional
