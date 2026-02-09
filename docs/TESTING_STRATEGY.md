# Testing Strategy — IDP Platform

## Approach

Phase 1 follows strict Test-Driven Development (TDD): every module's tests were written and committed **before** its implementation. Each feature branch's workflow was:

1. Write failing tests that define the expected behavior
2. Implement the minimum code to make them pass
3. Verify with `pytest -v`
4. Commit only after all tests pass

## Test Infrastructure

### Framework and Configuration

- **Framework**: pytest 8.3.4
- **Config file**: `pyproject.toml`
  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["."]
  testpaths = ["tests"]
  ```
- **HTTP client**: httpx 0.28.1 (available for async API testing in future phases)

### Database Test Isolation

Tests use a separate PostgreSQL database (`idp_platform_test` on port 5433). The `conftest.py` fixtures ensure full isolation:

- **`db_engine`**: Creates all tables before each test module, drops them after
- **`db_session`**: Opens a session, yields it, then rolls back and closes — no test data leaks between tests
- **`sample_document`**: Pre-creates a Document record for tests that need an existing document

```
Test function starts
  └── db_engine fixture: CREATE ALL tables
        └── db_session fixture: open session
              └── sample_document fixture: insert test record
                    └── Test runs
              └── session.rollback()
              └── session.close()
        └── DROP ALL tables
        └── engine.dispose()
```

### Test Fixtures File

`tests/conftest.py` — shared fixtures available to all test files:

| Fixture | Scope | Depends On | Provides |
|---------|-------|------------|----------|
| `db_engine` | function | — | SQLAlchemy engine with tables created |
| `db_session` | function | `db_engine` | SQLAlchemy session (rolled back after test) |
| `sample_document` | function | `db_session` | A Document record (filename: `test_doc.pdf`, type: `application/pdf`, size: 2048) |

### Test Fixture Files

| File | Purpose |
|------|---------|
| `tests/fixtures/sample_invoice.pdf` | 1-page synthetic invoice PDF (17,774 bytes) generated with Pillow. Contains text fields (invoice number, date, total) and a table with line items. Used by preprocessing tests. |

## Current Test Coverage

### Summary

```
26 tests across 5 test files — all passing
```

| Test File | Tests | Module Under Test |
|-----------|-------|-------------------|
| `test_database_crud.py` | 6 | `src/backend/db/crud.py`, `src/backend/db/models.py` |
| `test_jwt_handler.py` | 4 | `src/backend/auth/jwt_handler.py` |
| `test_rbac.py` | 4 | `src/backend/auth/rbac.py` |
| `test_file_upload.py` | 7 | `src/backend/ingestion/file_upload.py` |
| `test_preprocessing.py` | 5 | `src/backend/ingestion/preprocessing.py` |

### Test Details

#### `tests/unit/test_database_crud.py` — 6 tests

| Test | What It Verifies |
|------|-----------------|
| `TestDocumentCRUD::test_create_document` | Document is created with auto-generated `doc_` ID, correct filename, and default status `"uploaded"` |
| `TestDocumentCRUD::test_get_document` | A previously created document can be fetched by its ID |
| `TestDocumentCRUD::test_get_nonexistent_document_returns_none` | Querying a non-existent ID returns `None` (not an exception) |
| `TestDocumentCRUD::test_store_extracted_fields` | Multiple ExtractedField records are bulk-created and linked to a document, with correct field_name and confidence values |
| `TestUserCRUD::test_create_user` | User is created with auto-generated `usr_` ID, correct email, and bcrypt-hashed password (not plaintext) |
| `TestUserCRUD::test_get_user_by_email` | A previously created user can be fetched by email with correct name and role |

#### `tests/unit/test_jwt_handler.py` — 4 tests

| Test | What It Verifies |
|------|-----------------|
| `test_create_returns_string` | `create_access_token()` returns a non-empty string |
| `test_verify_valid_token` | A freshly created token can be decoded and contains the correct `sub` and `role` claims |
| `test_verify_invalid_token_raises` | Passing a garbage string to `verify_token()` raises an exception |
| `test_expired_token_raises` | A token created with a negative `expires_delta` (already expired) raises an exception on verification |

#### `tests/unit/test_rbac.py` — 4 tests

Uses `SimpleNamespace` objects as mock users with a `.role` attribute.

| Test | What It Verifies |
|------|-----------------|
| `test_admin_accesses_admin_routes` | An admin user passes `require_role(["admin"])` and is returned |
| `test_reviewer_blocked_from_admin` | A reviewer user is rejected by `require_role(["admin"])` with an exception |
| `test_enterprise_user_can_upload` | An enterprise_user passes `require_role(["enterprise_user", "admin"])` |
| `test_enterprise_user_blocked_from_review` | An enterprise_user is rejected by `require_role(["reviewer", "admin"])` |

#### `tests/unit/test_file_upload.py` — 7 tests

Uses a `MockUploadFile` class that simulates FastAPI's `UploadFile` interface with `filename`, `content_type`, `file` (self-reference), and `read()`.

| Test | What It Verifies |
|------|-----------------|
| `test_accept_pdf` | A `.pdf` file is accepted; original_filename and file_type are preserved |
| `test_accept_png` | A `.png` file is accepted |
| `test_accept_jpg` | A `.jpg` file is accepted |
| `test_reject_exe` | A `.exe` file raises `ValueError` with "File type not allowed" |
| `test_reject_oversized` | A file exceeding 50MB raises `ValueError` with "exceeds maximum" |
| `test_file_saved_to_disk` | After upload, the file exists on disk at the expected path with matching content |
| `test_unique_filenames` | Two uploads of the same original filename produce different stored filenames |

#### `tests/unit/test_preprocessing.py` — 5 tests

Requires `tests/fixtures/sample_invoice.pdf` and poppler (for pdf2image).

| Test | What It Verifies |
|------|-----------------|
| `test_pdf_to_images_returns_list_of_arrays` | `convert_pdf_to_images()` returns a non-empty list of NumPy arrays |
| `test_deskew_preserves_shape` | `deskew_image()` returns an image with positive dimensions |
| `test_denoise_reduces_std` | `denoise_image()` on random noise produces output with lower standard deviation |
| `test_grayscale_is_2d` | `to_grayscale()` converts a 3-channel image to a 2D array |
| `test_preprocess_document_returns_pages` | `preprocess_document()` returns `PreprocessedPage` objects with `original`, `processed` (2D) attributes |

## What Is Unit-Tested vs Integration-Tested

### Unit-Tested (Phase 1)

All 26 current tests are **unit tests**. They test individual functions and classes in isolation:

- **CRUD functions**: Tested against a real PostgreSQL test database, but each test is isolated via transaction rollback
- **JWT handler**: Tested in-process with no network calls
- **RBAC**: Tested with mock user objects (`SimpleNamespace`), no FastAPI request context
- **File upload**: Tested with `MockUploadFile` objects and a temp directory, no HTTP layer
- **Preprocessing**: Tested with a fixture PDF and synthetic NumPy arrays, no HTTP layer

### Not Yet Unit-Tested

| Component | Why | When |
|-----------|-----|------|
| API routes (`routes_auth.py`, `routes_upload.py`) | Routes were verified via manual smoke test (curl), not automated API tests | Phase 6 — integration tests with `httpx.AsyncClient` / `TestClient` |
| `main.py` startup event | Verified manually (tables created on boot) | Phase 6 |
| CORS middleware behavior | Development-only config, not critical to test | Phase 6 or production hardening |
| `list_documents()` CRUD function | Implemented but not directly tested; implicitly works if `create_document` works | Phase 2 (when list endpoint is added) |

### Integration-Tested (Manual Smoke Test)

The Phase 1 integration verification was a manual smoke test, not automated. The following sequence was verified via curl:

```
GET  /health                     → 200 {"status": "healthy"}
POST /api/auth/register          → 201 {id, email, name, role}
POST /api/auth/login             → 200 {accessToken, tokenType, user}
POST /api/documents/upload       → 201 {id, filename, originalFilename, fileType, fileSize, status}
```

This should be converted to an automated integration test in Phase 6.

## Testing Guidelines for Future Phases

### Phase 2: OCR and NLP Components

OCR and NLP modules should be tested with:

1. **Deterministic unit tests** — Test with known fixture documents where expected outputs are predefined:
   - `tests/fixtures/sample_invoice.pdf` already exists
   - Add fixtures for different document types (receipts, contracts, forms)
   - Assert that specific text strings are found in OCR output
   - Assert that specific entities (invoice_number, date, amount) are extracted by NER

2. **Confidence threshold tests** — Verify that confidence scores are within expected ranges:
   ```python
   def test_ocr_confidence_above_threshold(sample_pdf):
       result = ocr_engine.extract_text(sample_pdf)
       assert result.confidence > 0.7
   ```

3. **Fallback tests** — Verify that when Tesseract fails or returns low confidence, EasyOCR is invoked as fallback

4. **Layout region tests** — Verify that Detectron2/LayoutParser correctly identifies regions (header, table, body) on fixture documents

5. **Table extraction tests** — Use fixture PDFs with known tables and assert that LineItem records match expected values

### Phase 3: Validation and HITL

1. **Schema validation tests** — Define schemas for known document types and test that:
   - Valid fields pass validation
   - Invalid/missing fields are flagged with specific error messages
   - Confidence-based thresholds trigger HITL review

2. **Correction workflow tests** — Test the full correction cycle:
   ```python
   def test_correction_updates_field(db_session, sample_field):
       correction = submit_correction(db_session, field_id=sample_field.id,
                                       corrected_value="FIXED", reviewer_id=reviewer.id)
       assert correction.original_value == sample_field.field_value
       assert correction.corrected_value == "FIXED"
   ```

3. **Pipeline orchestration tests** — Test that the pipeline correctly chains steps and handles failures at each stage

### Phase 4: Analytics

1. **Metric computation tests** — Verify aggregation functions produce correct results for known datasets
2. **Prediction model tests** — Train on fixture data, verify predictions are within expected bounds
3. **Anomaly detection tests** — Inject known anomalies into fixture data, verify they are flagged

### Phase 5: Frontend (Done — No automated tests yet)

Phase 5 shipped without automated frontend tests. Verification was done manually via browser testing (see PHASE5_SUMMARY.md for the test flow). Future frontend testing should include:

1. **Component tests** — React Testing Library for individual components:
   ```javascript
   test('LoginPage toggles between login and register modes', () => {
     render(<LoginPage />);
     expect(screen.getByText('Sign in to continue')).toBeInTheDocument();
     fireEvent.click(screen.getByText('Register'));
     expect(screen.getByText('Create your account')).toBeInTheDocument();
   });
   ```

2. **API integration tests** — Mock API responses with `msw` (Mock Service Worker) and verify UI state:
   ```javascript
   test('UploadPage shows success after upload', async () => {
     server.use(rest.post('/api/documents/upload', (req, res, ctx) =>
       res(ctx.status(201), ctx.json({ id: 'doc_abc123', status: 'uploaded' }))
     ));
     // render, drop file, click upload, assert result card
   });
   ```

3. **Auth flow tests** — Verify login → redirect → session persistence → logout → redirect cycle

4. **Protected route tests** — Verify non-admin users cannot access `/admin` route

### Phase 6: End-to-End

1. **Automated smoke tests** — Convert the manual curl sequence into pytest tests using `httpx.AsyncClient`:
   ```python
   async def test_full_pipeline(client):
       # Register
       resp = await client.post("/api/auth/register", json={...})
       assert resp.status_code == 201

       # Login
       resp = await client.post("/api/auth/login", json={...})
       token = resp.json()["accessToken"]

       # Upload
       resp = await client.post("/api/documents/upload",
                                 headers={"Authorization": f"Bearer {token}"},
                                 files={"file": open("tests/fixtures/sample_invoice.pdf", "rb")})
       assert resp.status_code == 201
       doc_id = resp.json()["id"]

       # Process (Phase 2)
       # Validate (Phase 3)
       # Check analytics (Phase 4)
   ```

2. **BDD scenarios** — Cover the complete user journey: upload → extraction → validation → correction → analytics

## Running Tests

```bash
# Activate virtualenv
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/unit/test_database_crud.py -v

# Run with short traceback
pytest tests/ -v --tb=short

# Run a specific test class
pytest tests/unit/test_rbac.py::TestRBAC -v
```

### Prerequisites

- PostgreSQL 15 running on port 5433 (`pg_ctl -D /opt/homebrew/var/postgresql@15 -o "-p 5433" start`)
- Database `idp_platform_test` exists (`createdb -p 5433 idp_platform_test`)
- Virtualenv activated with all dependencies installed
- poppler installed (`brew install poppler`) — required by preprocessing tests
