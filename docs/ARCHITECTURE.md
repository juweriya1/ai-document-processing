# Architecture — IDP Platform

## System Overview

The Intelligent Document Processing (IDP) Platform is a monolithic but modular backend built with Python 3.11 and FastAPI. It processes uploaded documents (PDFs, images) through an ingestion-to-analytics pipeline. The frontend (React.js, not yet implemented) will connect via REST API with JWT authentication.

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                       │
│                      (Not implemented)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST / JSON
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                     │
│                    src/backend/main.py                      │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │   Auth   │  │   Documents  │  │   Health              │ │
│  │ /api/auth│  │/api/documents│  │   GET /health         │ │
│  └────┬─────┘  └──────┬───────┘  └───────────────────────┘ │
│       │               │                                     │
│  ┌────▼─────┐  ┌──────▼───────┐                            │
│  │   JWT    │  │  Ingestion   │                            │
│  │   RBAC   │  │  FileUpload  │                            │
│  │          │  │  Preprocess  │                            │
│  └────┬─────┘  └──────┬───────┘                            │
│       │               │                                     │
│       └───────┬───────┘                                     │
│               ▼                                             │
│  ┌────────────────────┐                                     │
│  │   Database (ORM)   │                                     │
│  │   SQLAlchemy +     │                                     │
│  │   PostgreSQL 15    │                                     │
│  └────────────────────┘                                     │
└─────────────────────────────────────────────────────────────┘
```

## Technology Stack (Phase 1)

| Layer | Technology | Version |
|-------|-----------|---------|
| Runtime | Python | 3.11.4 |
| Framework | FastAPI | 0.115.6 |
| Server | Uvicorn | 0.34.0 |
| ORM | SQLAlchemy | 2.0.36 |
| Database | PostgreSQL (Homebrew) | 15.14 |
| DB Adapter | psycopg2-binary | 2.9.10 |
| Auth | python-jose (JWT) | 3.3.0 |
| Password Hashing | passlib + bcrypt | 1.7.4 / 4.0.1 |
| Image Processing | OpenCV (headless) | 4.10.0.84 |
| PDF Conversion | pdf2image + poppler | 1.17.0 |
| Image Library | Pillow | 11.1.0 |
| Numerics | NumPy | 1.26.4 |
| Testing | pytest | 8.3.4 |
| HTTP Client | httpx | 0.28.1 |

## Backend Modules — Phase 1

The backend lives under `src/backend/` and is organized into four packages plus a top-level config and application entry point.

### `src/backend/config.py` — Configuration

Loads all settings from environment variables with sensible defaults. No `.env` file is auto-loaded; values fall back to hardcoded defaults suitable for local development.

| Setting | Default | Purpose |
|---------|---------|---------|
| `DATABASE_URL` | `postgresql://localhost:5433/idp_platform` | Production DB connection |
| `TEST_DATABASE_URL` | `postgresql://localhost:5433/idp_platform_test` | Test DB connection |
| `SECRET_KEY` | `dev-secret-key-not-for-production` | JWT signing key |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `UPLOAD_DIR` | `uploads` | File storage directory |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit |
| `ALLOWED_FILE_TYPES` | PDF, PNG, JPEG, DOC, DOCX MIME types | Accepted MIME types |
| `ALLOWED_EXTENSIONS` | `.pdf`, `.png`, `.jpg`, `.jpeg`, `.doc`, `.docx` | Accepted extensions |

### `src/backend/main.py` — Application Entry Point

- Creates the FastAPI app (title: "IDP Platform", version: "0.1.0")
- Adds CORS middleware (allow all origins — development only)
- Registers `auth_router` and `upload_router`
- On startup: creates all database tables via `Base.metadata.create_all(bind=engine)`
- Exposes `GET /health` returning `{"status": "healthy"}`

### `src/backend/auth/` — Authentication and Authorization

Two modules handle identity:

**`jwt_handler.py`** — Token lifecycle:
- `create_access_token(data, expires_delta)` — Encodes a JWT with `sub`, `role`, `user_id` claims and an `exp` timestamp
- `verify_token(token)` — Decodes and validates; raises HTTP 401 on failure
- `get_current_user(token)` — FastAPI dependency that extracts the current user dict from the Bearer token

**`rbac.py`** — Role-Based Access Control:
- `require_role(allowed_roles)` — Returns a callable that checks a user object's `.role` attribute; raises HTTP 403 if the role is not in the allowed list. Used in unit tests.
- `role_required(allowed_roles)` — Returns a FastAPI dependency that extracts the role from the JWT payload and enforces authorization. Used in route definitions.

Three roles exist: `admin`, `reviewer`, `enterprise_user`. Authorization rules implemented so far:

| Role | Can Register/Login | Can Upload | Can Access Admin Routes | Can Access Review Routes |
|------|--------------------|-----------|------------------------|-------------------------|
| `admin` | Yes | Yes | Yes | Yes |
| `reviewer` | Yes | Yes | No | Yes |
| `enterprise_user` | Yes | Yes | No | No |

### `src/backend/db/` — Database Layer

Three modules handle persistence:

**`database.py`** — Connection management:
- `engine` — SQLAlchemy engine bound to `DATABASE_URL`
- `SessionLocal` — Session factory (`autocommit=False`, `autoflush=False`)
- `get_db()` — FastAPI dependency generator that yields a session and closes it on completion

**`models.py`** — Seven ORM models, all using a shared `Base`:

| Model | Table | Primary Key | Key Fields |
|-------|-------|-------------|------------|
| `User` | `users` | `usr_` + 6 hex | email (unique, indexed), password_hash, name, role, created_at |
| `Document` | `documents` | `doc_` + 6 hex | filename, original_filename, file_type, file_size, status, uploaded_by (FK→User), uploaded_at, processed_at |
| `ExtractedField` | `extracted_fields` | `fld_` + 6 hex | document_id (FK→Document), field_name, field_value, confidence, created_at |
| `LineItem` | `line_items` | `lin_` + 6 hex | document_id (FK→Document), description, quantity, unit_price, total, created_at |
| `Correction` | `corrections` | `cor_` + 6 hex | document_id (FK→Document), field_id (FK→ExtractedField), original_value, corrected_value, reviewed_by (FK→User), created_at |
| `AnalyticsSummary` | `analytics_summaries` | auto-increment int | metric_name, metric_value, period, created_at |
| `SupplierMetric` | `supplier_metrics` | auto-increment int | supplier_name, total_documents, avg_confidence, risk_score, created_at |

Relationships: User→Documents, User→Corrections, Document→ExtractedFields, Document→LineItems, Document→Corrections, Correction→ExtractedField.

**`crud.py`** — Data access functions:

| Function | Purpose |
|----------|---------|
| `create_document(db, filename, original_filename, file_type, file_size, uploaded_by=None)` | Insert a Document record |
| `get_document(db, document_id)` | Fetch one Document or None |
| `list_documents(db, skip=0, limit=100)` | Paginated Document list |
| `store_extracted_fields(db, document_id, fields)` | Bulk-insert ExtractedField records from a list of dicts |
| `create_user(db, email, password, name, role)` | Insert a User with bcrypt-hashed password |
| `get_user_by_email(db, email)` | Fetch one User by email or None |
| `verify_password(plain_password, hashed_password)` | Compare plaintext against bcrypt hash |

### `src/backend/ingestion/` — Document Ingestion

Two modules handle file intake and preparation:

**`file_upload.py`** — Upload handling:
- `FileUpload` class validates file type (by extension), file size (against `MAX_FILE_SIZE_MB`), generates unique stored filenames (`doc_<12-hex-chars>.<ext>`), and writes content to the `uploads/` directory
- Returns a `DocumentMeta` dataclass with stored_filename, original_filename, file_type, file_size, file_path
- Handles both FastAPI `UploadFile` (via `file.file.read()`) and plain file objects (via `file.read()`)

**`preprocessing.py`** — Image preparation:
- `Preprocessing` class provides a four-step pipeline: PDF→images, grayscale, denoise, deskew
- `convert_pdf_to_images(pdf_path)` — Uses pdf2image at 300 DPI, returns list of NumPy arrays
- `to_grayscale(image)` — Converts RGB to grayscale via OpenCV
- `denoise_image(image)` — Applies 5x5 Gaussian blur
- `deskew_image(image)` — Computes rotation angle via `cv2.minAreaRect` on non-zero pixel coordinates, applies affine warp
- `preprocess_document(pdf_path)` — Full pipeline returning `list[PreprocessedPage]`, each with `page_number`, `original` (color), and `processed` (grayscale, denoised, deskewed)

### `src/backend/api/` — API Routes

**`routes_auth.py`** — Authentication endpoints:

| Method | Path | Auth | Request Body | Response | Status |
|--------|------|------|-------------|----------|--------|
| POST | `/api/auth/register` | None | `{email, password, name, role?}` | `{id, email, name, role}` | 201 |
| POST | `/api/auth/login` | None | `{email, password}` | `{accessToken, tokenType, user: {id, email, name, role}}` | 200 |

**`routes_upload.py`** — Document upload endpoint:

| Method | Path | Auth | Request Body | Response | Status |
|--------|------|------|-------------|----------|--------|
| POST | `/api/documents/upload` | Bearer JWT (enterprise_user, admin, reviewer) | multipart file | `{id, filename, originalFilename, fileType, fileSize, status}` | 201 |

## Modules Not Yet Implemented (Future Phases)

The following packages exist as empty `__init__.py` markers or as schema-only models with no business logic:

| Module | Phase | Purpose |
|--------|-------|---------|
| `src/backend/layout_engine/` | Phase 2 | LayoutParser + Detectron2 for document structure analysis |
| `src/backend/extraction/` | Phase 2 | spaCy NER + HuggingFace Transformers for field extraction |
| `src/backend/validation/` | Phase 3 | Schema validation + HITL correction workflow |
| `src/backend/pipeline/` | Phase 3 | End-to-end orchestration (upload → extract → validate → store) |
| `src/backend/analytics/` | Phase 4 | Plotly dashboards, scikit-learn predictions, anomaly detection |
| Frontend (React.js) | Phase 5 | 8 pages: Login, Dashboard, Upload, Processing, Validation, Review, Insights, Admin |

The ORM models `LineItem`, `Correction`, `AnalyticsSummary`, and `SupplierMetric` have table definitions but no CRUD functions or API endpoints yet. They exist to avoid schema migrations when those features are built.

## Database Architecture

PostgreSQL 15 (Homebrew) runs on port **5433** (the system-installed PostgreSQL 16 occupies port 5432).

Two databases exist:
- `idp_platform` — Application data
- `idp_platform_test` — Test data (tables created/dropped per test function)

Tables are auto-created on FastAPI startup via `Base.metadata.create_all()`. No migration tool (Alembic) is configured yet.

## Request Flow

```
Client
  │
  ▼
FastAPI (CORS middleware)
  │
  ├── GET /health ──────────────────────────► {"status": "healthy"}
  │
  ├── POST /api/auth/register ──► create_user() ──► DB ──► UserResponse
  │
  ├── POST /api/auth/login ─────► get_user_by_email()
  │                                 verify_password()
  │                                 create_access_token() ──► LoginResponse
  │
  └── POST /api/documents/upload
        │
        ├── role_required() ──► verify_token() ──► check role
        │
        ├── FileUpload.save_uploaded_file()
        │     ├── validate_file_type()
        │     ├── validate_file_size()
        │     └── write to uploads/
        │
        └── create_document() ──► DB ──► UploadResponse
```

The `Preprocessing` class is implemented and tested but not yet wired into any API endpoint. It will be invoked by the pipeline orchestrator in Phase 3, after OCR and extraction modules are built in Phase 2.
