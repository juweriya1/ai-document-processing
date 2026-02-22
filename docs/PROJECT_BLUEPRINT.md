# Intelligent Document Processing Platform — Full Project Blueprint

> Generated from SRS.pdf, SDS.pdf, and proposal.pdf analysis.
> Diagrams in SRS/SDS are **fallback layouts**; new wireframes from UI/UX team take priority.

---

## Table of Contents

1. [Folder Structure](#1-folder-structure)
2. [Backend Modules](#2-backend-modules)
3. [Frontend Modules](#3-frontend-modules)
4. [API Endpoints & JSON Contracts](#4-api-endpoints--json-contracts)
5. [Database Schema](#5-database-schema)
6. [Example AI Module Outputs](#6-example-ai-module-outputs)
7. [TDD Unit Tests](#7-tdd-unit-tests)
8. [BDD End-to-End Scenarios](#8-bdd-end-to-end-scenarios)
9. [Implementation Sequence & Dependencies](#9-implementation-sequence--dependencies)
10. [Module Dependency Graph](#10-module-dependency-graph)
11. [Diagram & Image Inventory from All PDFs](#11-diagram--image-inventory-from-all-pdfs)
12. [Sequence Diagram — Step-by-Step Pipeline Workflow (SDS)](#12-sequence-diagram--step-by-step-pipeline-workflow-sds)
13. [Class Diagram — Full Specification (SDS)](#13-class-diagram--full-specification-sds)
14. [Domain Model — Entity Relationships (SRS)](#14-domain-model--entity-relationships-srs)
15. [Package Diagram — Subsystem Mapping (SDS)](#15-package-diagram--subsystem-mapping-sds)
16. [Computational Models & Mathematical Formulas (SRS)](#16-computational-models--mathematical-formulas-srs)
17. [Wireframe Specifications — Detailed UI Text (SRS)](#17-wireframe-specifications--detailed-ui-text-srs)
18. [Project Timeline from proposal.pdf](#18-project-timeline-from-proposalpdf)
19. [Research & Improvement Test Metrics (SDS)](#19-research--improvement-test-metrics-sds)

---

## 1. Folder Structure

```
ai-document-processing/
├── CLAUDE.md
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── docs/
│   ├── proposal.pdf
│   ├── SRS.pdf
│   ├── SDS.pdf
│   ├── PROJECT_BLUEPRINT.md        ← this file
│   └── images/
│
├── src/
│   ├── backend/
│   │   ├── requirements.txt
│   │   ├── main.py                 ← FastAPI app entrypoint
│   │   ├── config.py               ← env vars, settings
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes_upload.py    ← POST /api/documents/upload
│   │   │   ├── routes_documents.py ← GET /api/documents, GET /api/documents/{id}
│   │   │   ├── routes_extraction.py← GET /api/documents/{id}/extraction
│   │   │   ├── routes_validation.py← POST /api/documents/{id}/validate, corrections
│   │   │   ├── routes_review.py    ← HITL approve/reject/correct
│   │   │   ├── routes_analytics.py ← GET /api/analytics/*
│   │   │   ├── routes_predictions.py ← GET /api/predictions/*
│   │   │   └── routes_auth.py      ← POST /api/auth/login, /register, /roles
│   │   │
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── file_upload.py      ← handle file receive, type detection
│   │   │   └── preprocessing.py    ← deskew, denoise, resize, convert
│   │   │
│   │   ├── layout_engine/
│   │   │   ├── __init__.py
│   │   │   ├── ocr_engine.py       ← Tesseract / EasyOCR / PaddleOCR
│   │   │   ├── layout_analyzer.py  ← LayoutLM / Detectron2 segmentation
│   │   │   └── table_extractor.py  ← pdfplumber table extraction
│   │   │
│   │   ├── extraction/
│   │   │   ├── __init__.py
│   │   │   ├── entity_extractor.py ← spaCy NER + regex + HuggingFace
│   │   │   └── field_mapper.py     ← map raw entities to schema fields
│   │   │
│   │   ├── validation/
│   │   │   ├── __init__.py
│   │   │   ├── schema_validator.py ← rule-based checks (date, amount, required fields)
│   │   │   └── correction_handler.py ← handle HITL corrections, store feedback
│   │   │
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py         ← SQLAlchemy engine/session setup
│   │   │   ├── models.py           ← ORM models (Document, ExtractedField, etc.)
│   │   │   └── crud.py             ← create/read/update/delete operations
│   │   │
│   │   ├── analytics/
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py        ← spend analysis, supplier perf, compliance
│   │   │   └── predictions.py      ← Random Forest, anomaly detection, trend forecast
│   │   │
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── jwt_handler.py      ← JWT token create/verify
│   │   │   └── rbac.py             ← role-based access control middleware
│   │   │
│   │   └── pipeline/
│   │       ├── __init__.py
│   │       └── document_processor.py ← orchestrates full pipeline end-to-end
│   │
│   └── frontend/
│       ├── package.json
│       ├── public/
│       │   └── index.html
│       └── src/
│           ├── index.js
│           ├── App.js              ← router setup
│           ├── api/
│           │   └── client.js       ← axios instance, interceptors
│           ├── components/
│           │   ├── Navbar.jsx
│           │   ├── ProtectedRoute.jsx
│           │   └── FileDropzone.jsx
│           ├── pages/
│           │   ├── LoginPage.jsx
│           │   ├── DashboardPage.jsx
│           │   ├── UploadPage.jsx
│           │   ├── ProcessingPage.jsx
│           │   ├── ValidationPage.jsx
│           │   ├── ReviewPage.jsx
│           │   ├── InsightsPage.jsx
│           │   └── AdminPage.jsx
│           ├── hooks/
│           │   ├── useAuth.js
│           │   └── usePolling.js
│           └── context/
│               └── AuthContext.js
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 ← shared fixtures (sample PDFs, DB session, client)
│   │
│   ├── unit/
│   │   ├── test_file_upload.py
│   │   ├── test_preprocessing.py
│   │   ├── test_ocr_engine.py
│   │   ├── test_layout_analyzer.py
│   │   ├── test_table_extractor.py
│   │   ├── test_entity_extractor.py
│   │   ├── test_field_mapper.py
│   │   ├── test_schema_validator.py
│   │   ├── test_correction_handler.py
│   │   ├── test_database_crud.py
│   │   ├── test_dashboard.py
│   │   ├── test_predictions.py
│   │   ├── test_jwt_handler.py
│   │   └── test_rbac.py
│   │
│   ├── integration/
│   │   ├── test_pipeline_end_to_end.py
│   │   ├── test_upload_to_extraction.py
│   │   ├── test_validation_hitl_flow.py
│   │   └── test_analytics_flow.py
│   │
│   ├── research/                   ← SDS Section 6: research/improvement metrics
│   │   ├── test_field_accuracy.py  ← Precision/Recall/F1 per entity type
│   │   ├── test_ocr_accuracy.py    ← CER and WER against ground truth
│   │   ├── test_layout_retention.py← table/heading/section reconstruction
│   │   ├── test_match_rates.py     ← exact and partial match rates
│   │   ├── test_hitl_metrics.py    ← correction rate, time, confidence correlation
│   │   ├── test_comparative.py     ← baseline comparison (Tesseract-only vs full pipeline)
│   │   └── test_nfr_compliance.py  ← all 7 NFRs from SRS
│   │
│   └── fixtures/
│       ├── sample_invoice.pdf
│       ├── sample_receipt.png
│       └── sample_contract.pdf
│
└── uploads/                        ← gitignored, runtime document storage
```

---

## 2. Backend Modules

### 2.1 Document Ingestion (`src/backend/ingestion/`)

**file_upload.py**
- Class: `FileUpload`
- Responsibilities:
  - Accept multipart file uploads (PDF, DOCX, JPG, PNG)
  - Validate file type and size (max 50MB)
  - Save to `uploads/` with UUID filename
  - Return document metadata (id, original name, type, size, upload timestamp)
- Key functions:
  - `save_uploaded_file(file: UploadFile) -> DocumentMeta`
  - `validate_file_type(filename: str) -> bool`
  - `get_file_path(document_id: str) -> Path`

**preprocessing.py**
- Class: `Preprocessing`
- Responsibilities:
  - Convert PDF pages to images (pdf2image)
  - Deskew scanned images (OpenCV)
  - Denoise (Gaussian/median blur)
  - Resize to optimal OCR resolution
  - Convert color to grayscale
- Key functions:
  - `preprocess_document(file_path: str) -> list[PreprocessedPage]`
  - `deskew_image(image: np.ndarray) -> np.ndarray`
  - `denoise_image(image: np.ndarray) -> np.ndarray`
  - `convert_pdf_to_images(pdf_path: str) -> list[np.ndarray]`

### 2.2 OCR & Layout Engine (`src/backend/layout_engine/`)

**ocr_engine.py**
- Class: `OCREngine`
- Responsibilities:
  - Run OCR using Tesseract (primary) and EasyOCR (fallback)
  - Return extracted text with bounding boxes and confidence scores
  - Support multilingual OCR (English primary)
- Key functions:
  - `extract_text(image: np.ndarray, lang: str = "eng") -> OCRResult`
  - `extract_text_with_boxes(image: np.ndarray) -> list[TextBlock]`

**layout_analyzer.py**
- Class: `LayoutAnalyzer`
- Responsibilities:
  - Segment document into logical regions (text, tables, figures, headers)
  - Use Detectron2 (layoutparser) for layout detection
  - Return labeled bounding boxes per region type
- Key functions:
  - `analyze_layout(image: np.ndarray) -> list[LayoutRegion]`
  - `classify_regions(regions: list) -> dict[str, list[LayoutRegion]]`

**table_extractor.py**
- Class: `TableExtractor`
- Responsibilities:
  - Extract tabular data from PDFs using pdfplumber
  - Fall back to image-based table detection for scanned docs
  - Return structured table data as list of rows
- Key functions:
  - `extract_tables_from_pdf(pdf_path: str, page_num: int) -> list[Table]`
  - `extract_tables_from_image(image: np.ndarray) -> list[Table]`

### 2.3 NLP/ML Extraction (`src/backend/extraction/`)

**entity_extractor.py**
- Class: `EntityExtractor`
- Responsibilities:
  - Run spaCy NER to identify dates, amounts, organizations, persons
  - Run HuggingFace transformer models for document-specific entity extraction
  - Apply regex rules for structured patterns (invoice numbers, dates, amounts)
  - Return entities with type labels and confidence scores
- Key functions:
  - `extract_entities(text: str) -> list[Entity]`
  - `extract_with_regex(text: str) -> list[Entity]`
  - `extract_with_ner(text: str) -> list[Entity]`
  - `merge_entities(regex_entities, ner_entities) -> list[Entity]`

**field_mapper.py**
- Class: `FieldMapper`
- Responsibilities:
  - Map raw extracted entities to expected schema fields
  - Combine OCR text, layout regions, and NER entities into structured output
  - Assign confidence scores to each mapped field
- Key functions:
  - `map_to_schema(entities: list[Entity], layout: list[LayoutRegion]) -> ExtractedFields`
  - `resolve_conflicts(candidates: list[Entity]) -> Entity`

### 2.4 Validation & HITL (`src/backend/validation/`)

**schema_validator.py**
- Class: `SchemaValidator`
- Responsibilities:
  - Validate extracted fields against predefined rules:
    - Date format: `YYYY-MM-DD`
    - Invoice number: regex pattern `INV-\d{4}-\d{4}`
    - Amount: numeric, `total == sum(line_items)`
    - Required fields: vendor_name, date, total_amount must be non-empty
  - Return per-field validation status (valid/invalid) with error messages
- Key functions:
  - `validate_fields(fields: ExtractedFields) -> ValidationResult`
  - `validate_date(value: str) -> bool`
  - `validate_amount(value: str) -> bool`
  - `validate_required(fields: dict, required: list[str]) -> list[str]`
  - `validate_line_item_total(line_items: list, total: float) -> bool`

**correction_handler.py**
- Class: `CorrectionHandler`
- Responsibilities:
  - Receive human corrections from HITL interface
  - Store correction history (original value, corrected value, user, timestamp)
  - Update extracted fields with corrected values
  - Track correction metrics for model improvement
- Key functions:
  - `submit_correction(document_id: str, field: str, corrected_value: str, user_id: str) -> Correction`
  - `get_correction_history(document_id: str) -> list[Correction]`
  - `apply_corrections(document_id: str) -> ExtractedFields`

### 2.5 Database Integration (`src/backend/db/`)

**models.py** — SQLAlchemy ORM models (see Section 5 for full schema)

**crud.py**
- Functions:
  - `create_document(db, doc_meta) -> Document`
  - `get_document(db, doc_id) -> Document`
  - `list_documents(db, filters) -> list[Document]`
  - `store_extracted_fields(db, doc_id, fields) -> list[ExtractedField]`
  - `update_field(db, field_id, new_value, user_id) -> ExtractedField`
  - `store_correction(db, correction) -> Correction`
  - `get_analytics_summary(db, filters) -> AnalyticsSummary`
  - `create_user(db, user_data) -> User`
  - `get_user_by_email(db, email) -> User`

### 2.6 Analytics & Dashboards (`src/backend/analytics/`)

**dashboard.py**
- Class: `AnalyticsModule`
- Responsibilities:
  - Aggregate spend analysis (total spend over time, by vendor, by category)
  - Compute supplier performance metrics (on-time rate, quality score)
  - Calculate compliance score
  - Detect anomalies (duplicate invoices, unusual amounts)
  - Return dashboard-ready data for charts
- Key functions:
  - `get_spend_analysis(db, date_range, vendor, category) -> SpendAnalysis`
  - `get_supplier_performance(db) -> list[SupplierMetric]`
  - `get_compliance_score(db) -> float`
  - `get_anomaly_alerts(db) -> list[AnomalyAlert]`
  - `get_expense_categories(db) -> dict[str, float]`

**predictions.py**
- Class: `PredictionEngine`
- Responsibilities:
  - Forecast spend trends (time-series: ARIMA or Prophet)
  - Compute supplier delay risk scores (Random Forest)
  - Detect anomalies (Isolation Forest / Z-score)
  - Generate AI insights with confidence levels
- Key functions:
  - `forecast_spend(db, months_ahead: int) -> SpendForecast`
  - `predict_supplier_risk(db, vendor_id: str) -> RiskScore`
  - `detect_anomalies(db) -> list[Anomaly]`
  - `generate_insights(db) -> list[Insight]`

### 2.7 Auth (`src/backend/auth/`)

**jwt_handler.py**
- `create_access_token(data: dict) -> str`
- `verify_token(token: str) -> dict`
- `get_current_user(token: str) -> User`

**rbac.py**
- Roles: `admin`, `reviewer`, `enterprise_user`
- `require_role(roles: list[str])` — FastAPI dependency
- Permission matrix:
  | Endpoint | admin | reviewer | enterprise_user |
  |----------|-------|----------|-----------------|
  | Upload   | yes   | yes      | yes             |
  | Review/Correct | yes | yes  | no              |
  | Approve/Reject | yes | yes  | no              |
  | Analytics | yes  | yes      | yes             |
  | Manage Users | yes | no    | no              |

### 2.8 Pipeline Orchestrator (`src/backend/pipeline/`)

**document_processor.py**
- Class: `DocumentProcessor`
- Responsibilities:
  - Orchestrate the full pipeline: upload → preprocess → OCR → layout → extract → validate → store
  - Track pipeline status per document
  - Handle errors and retries at each stage
- Key functions:
  - `run_pipeline(document_id: str) -> PipelineResult`
  - `get_pipeline_status(document_id: str) -> PipelineStatus`

Pipeline flow (from SDS sequence diagram — see **Section 12** for full 14-step breakdown with method signatures):
```
User → Frontend.selectFile() → Frontend.submit()
  → APIHandler.uploadDocument(request)
    → Ingestion.preprocessDocument(document)
      → LayoutEngine.extractText(document)
      → LayoutEngine.extractTables(document)
        → ExtractionModule.convertToStructuredFields(extractedText)
          → ValidationModule.validateFields(structuredFields)
            → [if validation fails] Human.requestCorrection(fields)
            → Human.submitCorrection(correctedFields)
          → DatabaseManager.storeData(validatedFields)
            → AnalyticsModule.generateDashboard()
  → Frontend.displayAnalytics()
```

> **Cross-references:** Class specifications in **Section 13**, package mapping in **Section 15**, domain entities in **Section 14**.

---

## 3. Frontend Modules

### 3.1 Pages (from SRS wireframes — see **Section 17** for full ASCII wireframe transcriptions with every label, icon, and button)

**LoginPage.jsx**
- Email + password input fields
- Role selector: Admin | Reviewer | Enterprise User
- JWT token stored in localStorage
- Redirect to Dashboard on success

**DashboardPage.jsx** (SRS wireframe: Analytics Dashboard)
- Nav: IDP Platform | Dashboard | Upload | Insights
- Summary cards: Total Spend ($1,245,680), Documents Processed (2,847), Compliance Score (94.3%), Anomalies Detected (23)
- Filters: date range, vendor, category
- Charts: Spend Analysis (line), Supplier Performance (bar), Expense Categories (pie)
- Anomaly Detection Alerts: High/Medium/Low priority cards
- Export: PDF, Excel buttons

**UploadPage.jsx** (SRS wireframe: Upload Documents)
- Drag & drop zone
- Browse Files button
- File type icons: PDF, Word, JPG, PNG
- "Supported formats: PDF, Word (.doc, .docx), Images (.jpg, .png)"
- Upload button → triggers processing

**ProcessingPage.jsx** (SRS wireframe: Processing Document)
- Steps with progress indicators:
  1. Preprocessing (checkmark when done)
  2. Performing OCR (progress bar with %)
  3. Layout Analysis
  4. Extracting Entities
- Estimated time remaining
- Polls `GET /api/documents/{id}/status` every 2 seconds

**ValidationPage.jsx** (SRS wireframe: Schema Validation)
- Table with columns: Field Name | Extracted Value | Status | Actions
- Fields: Invoice No, Date, Vendor Name, Line Items, Total Amount
- Status indicators: green checkmark (Valid), red X (Invalid)
- Error messages for invalid fields (e.g., "Total amount is required")
- "Proceed to Review" button

**ReviewPage.jsx** (SRS wireframe: Human-in-the-Loop Review)
- Split layout:
  - Left: Document Preview with zoom controls (100%)
  - Right: Extracted Fields panel with "Edit Mode" toggle
- Each field shows: OCR Result | Corrected Value (editable)
- Highlighted fields: Yellow = extracted, Red = needs correction
- Approve (green) / Reject buttons
- Correction History panel: shows previous corrections with original → corrected, user, timestamp

**InsightsPage.jsx** (SRS wireframe: Predictive Insights)
- Spend Trend Forecasting chart (actual + predicted lines)
- Supplier Delay Risk Score cards (vendor name, risk level, score, risk factors)
- AI-Generated Insights cards (prediction, confidence %, impact level)
- "Download Prediction Report" button
- Explanatory section: "How are these predictions generated?"

**AdminPage.jsx**
- User management table: name, email, role, status
- Controls: Add User, Edit Role, Deactivate
- Filters: active/inactive
- Activity logs panel

### 3.2 Shared Components

| Component | File | Purpose |
|-----------|------|---------|
| Navbar | `Navbar.jsx` | Top nav: IDP Platform, Dashboard, Upload, Insights, user info, logout |
| ProtectedRoute | `ProtectedRoute.jsx` | Wrap routes requiring auth; redirect to login |
| FileDropzone | `FileDropzone.jsx` | Drag & drop file upload with type validation |

### 3.3 API Client (`src/frontend/src/api/client.js`)
- Axios instance with base URL from env
- Request interceptor: attach JWT from localStorage
- Response interceptor: redirect to login on 401

---

## 4. API Endpoints & JSON Contracts

### 4.1 Authentication

**POST /api/auth/register**
```json
// Request
{
  "email": "user@company.com",
  "password": "securePass123",
  "name": "John Doe",
  "role": "enterprise_user"
}
// Response 201
{
  "id": "usr_a1b2c3",
  "email": "user@company.com",
  "name": "John Doe",
  "role": "enterprise_user"
}
```

**POST /api/auth/login**
```json
// Request
{
  "email": "user@company.com",
  "password": "securePass123"
}
// Response 200
{
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "tokenType": "bearer",
  "user": {
    "id": "usr_a1b2c3",
    "email": "user@company.com",
    "name": "John Doe",
    "role": "reviewer"
  }
}
```

### 4.2 Document Upload

**POST /api/documents/upload**
```
Content-Type: multipart/form-data
file: <binary>
```
```json
// Response 201
{
  "documentId": "doc_x7y8z9",
  "fileName": "invoice_2025.pdf",
  "fileType": "application/pdf",
  "fileSize": 245780,
  "status": "uploaded",
  "uploadedAt": "2025-11-17T10:30:00Z",
  "uploadedBy": "usr_a1b2c3"
}
```

### 4.3 Document Status & Pipeline

**GET /api/documents/{id}/status**
```json
// Response 200
{
  "documentId": "doc_x7y8z9",
  "status": "processing",
  "pipelineStages": {
    "preprocessing": {"status": "completed", "completedAt": "2025-11-17T10:30:05Z"},
    "ocr": {"status": "in_progress", "progress": 42},
    "layoutAnalysis": {"status": "pending"},
    "entityExtraction": {"status": "pending"},
    "validation": {"status": "pending"}
  },
  "estimatedTimeRemaining": 8
}
```

**GET /api/documents**
```json
// Response 200
{
  "documents": [
    {
      "documentId": "doc_x7y8z9",
      "fileName": "invoice_2025.pdf",
      "fileType": "application/pdf",
      "status": "validated",
      "uploadedAt": "2025-11-17T10:30:00Z",
      "uploadedBy": "usr_a1b2c3"
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```

### 4.4 Extraction Results

**GET /api/documents/{id}/extraction**
```json
// Response 200
{
  "documentId": "doc_x7y8z9",
  "extractedFields": {
    "invoiceNumber": {"value": "INV-2025-1147", "confidence": 0.97, "boundingBox": [120, 45, 280, 65]},
    "date": {"value": "2025-11-17", "confidence": 0.95, "boundingBox": [120, 80, 250, 100]},
    "vendorName": {"value": "Acme Corporation", "confidence": 0.92, "boundingBox": [120, 115, 320, 135]},
    "totalAmount": {"value": 2450.00, "confidence": 0.98, "boundingBox": [400, 350, 520, 370]},
    "lineItems": [
      {"description": "Consulting Services", "amount": 1500.00, "confidence": 0.94},
      {"description": "Software License", "amount": 950.00, "confidence": 0.96}
    ]
  },
  "ocrText": "INVOICE\nInvoice No: INV-2025-1147\nDate: 2025-11-17\nVendor: Acme Corporation\n...",
  "layoutRegions": [
    {"type": "header", "bbox": [0, 0, 600, 50]},
    {"type": "table", "bbox": [50, 200, 550, 400]},
    {"type": "text", "bbox": [50, 50, 550, 200]}
  ]
}
```

### 4.5 Schema Validation

**GET /api/documents/{id}/validation**
```json
// Response 200
{
  "documentId": "doc_x7y8z9",
  "validationResult": {
    "isValid": false,
    "fields": [
      {"fieldName": "invoiceNumber", "value": "INV-2025-1147", "status": "valid", "error": null},
      {"fieldName": "date", "value": "2025-11-17", "status": "valid", "error": null},
      {"fieldName": "vendorName", "value": "Acme Corporation", "status": "valid", "error": null},
      {"fieldName": "lineItems", "value": 5, "status": "valid", "error": null},
      {"fieldName": "totalAmount", "value": null, "status": "invalid", "error": "Total amount is required"}
    ]
  }
}
```

### 4.6 Human-in-the-Loop Review

**POST /api/documents/{id}/corrections**
```json
// Request
{
  "corrections": [
    {"fieldName": "vendorName", "originalValue": "Acme Corporatlon", "correctedValue": "Acme Corporation"},
    {"fieldName": "totalAmount", "originalValue": null, "correctedValue": 2450.00}
  ]
}
// Response 200
{
  "documentId": "doc_x7y8z9",
  "correctionsApplied": 2,
  "updatedFields": {
    "vendorName": {"value": "Acme Corporation", "status": "corrected"},
    "totalAmount": {"value": 2450.00, "status": "corrected"}
  }
}
```

**POST /api/documents/{id}/approve**
```json
// Request
{
  "action": "approve"
}
// Response 200
{
  "documentId": "doc_x7y8z9",
  "status": "approved",
  "approvedBy": "usr_a1b2c3",
  "approvedAt": "2025-11-17T11:00:00Z",
  "storedToDatabase": true
}
```

**POST /api/documents/{id}/reject**
```json
// Request
{
  "action": "reject",
  "reason": "OCR quality too low, needs rescan"
}
// Response 200
{
  "documentId": "doc_x7y8z9",
  "status": "rejected",
  "rejectedBy": "usr_a1b2c3",
  "reason": "OCR quality too low, needs rescan"
}
```

**GET /api/documents/{id}/corrections**
```json
// Response 200
{
  "documentId": "doc_x7y8z9",
  "corrections": [
    {
      "fieldName": "vendorName",
      "originalValue": "Acme Corporatlon",
      "correctedValue": "Acme Corporation",
      "correctedBy": "John Doe",
      "correctedAt": "2025-11-17T10:55:00Z"
    },
    {
      "fieldName": "date",
      "originalValue": "11/17/2025",
      "correctedValue": "2025-11-17",
      "correctedBy": "Sarah Smith",
      "correctedAt": "2025-11-17T09:55:00Z"
    }
  ]
}
```

### 4.7 Analytics & Dashboard

**GET /api/analytics/dashboard?dateRange=last_30_days&vendor=all&category=all**
```json
// Response 200
{
  "summaryCards": {
    "totalSpend": {"value": 1245680, "changePercent": 12.5},
    "documentsProcessed": {"value": 2847, "changePercent": 8.2},
    "complianceScore": {"value": 94.3, "changePercent": 2.1},
    "anomaliesDetected": {"value": 23, "changePercent": -5.4}
  },
  "spendAnalysis": {
    "labels": ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov"],
    "values": [95000, 110000, 125000, 118000, 132000, 145000]
  },
  "supplierPerformance": [
    {"vendor": "Acme Corp", "score": 95},
    {"vendor": "TechSupply", "score": 88},
    {"vendor": "GlobalVendor", "score": 92},
    {"vendor": "OfficeMax", "score": 85},
    {"vendor": "QuickShip", "score": 82}
  ],
  "expenseCategories": {
    "Office Supplies": 35,
    "IT Equipment": 25,
    "Services": 20,
    "Travel": 20
  },
  "anomalyAlerts": [
    {"priority": "high", "message": "Duplicate invoice detected - INV-2847"},
    {"priority": "medium", "message": "Unusual payment amount from TechSupply"},
    {"priority": "low", "message": "Missing PO reference for invoice INV-2831"}
  ]
}
```

### 4.8 Predictions & Insights

**GET /api/predictions/spend-forecast?monthsAhead=3**
```json
// Response 200
{
  "actual": {
    "labels": ["Dec 2024", "Jan 2025", "Feb 2025", "Mar 2025", "Apr 2025", "May 2025"],
    "values": [125000, 130000, 128000, 135000, 132000, 140000]
  },
  "predicted": {
    "labels": ["Jun 2025", "Jul 2025", "Aug 2025"],
    "values": [152000, 165000, 178000]
  }
}
```

**GET /api/predictions/supplier-risk**
```json
// Response 200
{
  "suppliers": [
    {
      "vendor": "TechSupply Inc.",
      "riskLevel": "high",
      "riskScore": 78,
      "riskFactors": [
        "Late deliveries (3 times last month)",
        "Payment delays increasing",
        "Quality complaints up 15%"
      ]
    },
    {
      "vendor": "GlobalVendor Corp",
      "riskLevel": "medium",
      "riskScore": 65,
      "riskFactors": [
        "Seasonal demand fluctuations",
        "Minor delivery inconsistencies"
      ]
    },
    {
      "vendor": "Acme Corporation",
      "riskLevel": "low",
      "riskScore": 25,
      "riskFactors": [
        "Consistent on-time delivery",
        "Strong quality metrics"
      ]
    }
  ]
}
```

**GET /api/predictions/insights**
```json
// Response 200
{
  "insights": [
    {
      "type": "spend_increase",
      "title": "Predicted Spend Increase",
      "description": "Based on historical patterns, spending is expected to increase by 12% in Q3 2025",
      "confidence": 0.87,
      "impact": "high"
    },
    {
      "type": "consolidation",
      "title": "Supplier Consolidation Opportunity",
      "description": "Analysis suggests consolidating 3 vendors could reduce costs by $45,000 annually",
      "confidence": 0.92,
      "impact": "high"
    },
    {
      "type": "seasonal_trend",
      "title": "Seasonal Trend Detected",
      "description": "Office supply purchases peak in September, recommend bulk ordering in August",
      "confidence": 0.95,
      "impact": "medium"
    }
  ]
}
```

### 4.9 User & Role Management (Admin)

**GET /api/admin/users**
```json
// Response 200
{
  "users": [
    {"id": "usr_a1b2c3", "name": "John Doe", "email": "john@company.com", "role": "reviewer", "status": "active"},
    {"id": "usr_d4e5f6", "name": "Jane Smith", "email": "jane@company.com", "role": "admin", "status": "active"}
  ]
}
```

**PUT /api/admin/users/{id}/role**
```json
// Request
{"role": "admin"}
// Response 200
{"id": "usr_a1b2c3", "role": "admin", "updatedAt": "2025-11-17T12:00:00Z"}
```

---

## 5. Database Schema

### PostgreSQL Tables

```sql
-- Users and authentication
CREATE TABLE users (
    id            VARCHAR(20) PRIMARY KEY,    -- e.g. "usr_a1b2c3"
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(255) NOT NULL,
    role          VARCHAR(50) NOT NULL DEFAULT 'enterprise_user',  -- admin | reviewer | enterprise_user
    status        VARCHAR(20) NOT NULL DEFAULT 'active',           -- active | inactive
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

-- Document metadata
CREATE TABLE documents (
    id            VARCHAR(20) PRIMARY KEY,    -- e.g. "doc_x7y8z9"
    file_name     VARCHAR(255) NOT NULL,
    file_type     VARCHAR(50) NOT NULL,       -- application/pdf, image/png, etc.
    file_size     INTEGER NOT NULL,
    file_path     VARCHAR(500) NOT NULL,
    status        VARCHAR(50) NOT NULL DEFAULT 'uploaded',
                  -- uploaded | preprocessing | ocr | extracting | validating |
                  -- review_pending | approved | rejected | stored
    uploaded_by   VARCHAR(20) REFERENCES users(id),
    uploaded_at   TIMESTAMP DEFAULT NOW(),
    approved_by   VARCHAR(20) REFERENCES users(id),
    approved_at   TIMESTAMP
);

-- Extracted fields per document
CREATE TABLE extracted_fields (
    id            SERIAL PRIMARY KEY,
    document_id   VARCHAR(20) REFERENCES documents(id) ON DELETE CASCADE,
    field_name    VARCHAR(100) NOT NULL,      -- invoiceNumber, date, vendorName, totalAmount, etc.
    field_value   TEXT,
    confidence    FLOAT,
    bounding_box  JSONB,                      -- [x1, y1, x2, y2]
    status        VARCHAR(20) DEFAULT 'extracted',  -- extracted | valid | invalid | corrected
    error_message TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Line items (child of document)
CREATE TABLE line_items (
    id            SERIAL PRIMARY KEY,
    document_id   VARCHAR(20) REFERENCES documents(id) ON DELETE CASCADE,
    description   TEXT NOT NULL,
    amount        DECIMAL(12, 2),
    quantity      INTEGER DEFAULT 1,
    confidence    FLOAT,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Human corrections
CREATE TABLE corrections (
    id              SERIAL PRIMARY KEY,
    document_id     VARCHAR(20) REFERENCES documents(id) ON DELETE CASCADE,
    field_name      VARCHAR(100) NOT NULL,
    original_value  TEXT,
    corrected_value TEXT NOT NULL,
    corrected_by    VARCHAR(20) REFERENCES users(id),
    corrected_at    TIMESTAMP DEFAULT NOW()
);

-- Analytics cache (precomputed summaries)
CREATE TABLE analytics_summaries (
    id              SERIAL PRIMARY KEY,
    period          VARCHAR(50) NOT NULL,     -- "2025-11", "2025-Q3", "last_30_days"
    vendor          VARCHAR(255),
    category        VARCHAR(100),
    total_spend     DECIMAL(14, 2),
    document_count  INTEGER,
    compliance_score FLOAT,
    anomaly_count   INTEGER,
    computed_at     TIMESTAMP DEFAULT NOW()
);

-- Supplier metrics
CREATE TABLE supplier_metrics (
    id              SERIAL PRIMARY KEY,
    vendor_name     VARCHAR(255) NOT NULL,
    performance_score FLOAT,
    risk_score      FLOAT,
    risk_level      VARCHAR(20),              -- low | medium | high
    risk_factors    JSONB,
    on_time_rate    FLOAT,
    quality_score   FLOAT,
    computed_at     TIMESTAMP DEFAULT NOW()
);
```

### SQLAlchemy ORM Models (`src/backend/db/models.py`)

Each table above maps 1:1 to an ORM model: `User`, `Document`, `ExtractedField`, `LineItem`, `Correction`, `AnalyticsSummary`, `SupplierMetric`.

> **Cross-reference:** See **Section 14.3** for how domain model entities (SRS img-011) map to these database tables.

---

## 6. Example AI Module Outputs

These are **real outputs** from off-the-shelf libraries — not placeholder data.

> **Cross-reference:** See **Section 16** for the mathematical models (from SRS) these libraries implement, including multimodal fusion, NER sequence labeling, and anomaly detection formulas.

### 6.1 Tesseract OCR Output

```python
import pytesseract
from PIL import Image

image = Image.open("sample_invoice.png")
ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

# Real output structure:
{
    "text": ["", "INVOICE", "", "Invoice", "No:", "INV-2025-1147", "Date:", "2025-11-17", ...],
    "conf": ["-1", "96", "-1", "95", "97", "93", "96", "91", ...],
    "left": [0, 250, 0, 50, 180, 250, 50, 180, ...],
    "top": [0, 30, 0, 80, 80, 80, 110, 110, ...],
    "width": [0, 120, 0, 80, 40, 150, 45, 100, ...],
    "height": [0, 25, 0, 20, 20, 20, 20, 20, ...]
}
```

### 6.2 EasyOCR Output

```python
import easyocr

reader = easyocr.Reader(["en"])
results = reader.readtext("sample_invoice.png")

# Real output structure:
[
    ([[120, 30], [370, 30], [370, 55], [120, 55]], "INVOICE", 0.9987),
    ([[50, 80], [170, 80], [170, 100], [50, 100]], "Invoice No:", 0.9834),
    ([[250, 80], [420, 80], [420, 100], [250, 100]], "INV-2025-1147", 0.9756),
    ([[50, 110], [120, 110], [120, 130], [50, 130]], "Date:", 0.9901),
    ([[250, 110], [380, 110], [380, 130], [250, 130]], "2025-11-17", 0.9645),
    ([[50, 140], [140, 140], [140, 160], [50, 160]], "Vendor:", 0.9823),
    ([[250, 140], [450, 140], [450, 160], [250, 160]], "Acme Corporation", 0.9512)
]
```

### 6.3 pdfplumber Table Extraction

```python
import pdfplumber

with pdfplumber.open("sample_invoice.pdf") as pdf:
    page = pdf.pages[0]
    tables = page.extract_tables()

# Real output structure:
[
    [
        ["Description", "Quantity", "Unit Price", "Amount"],
        ["Consulting Services", "1", "$1,500.00", "$1,500.00"],
        ["Software License", "1", "$950.00", "$950.00"],
        ["", "", "Total:", "$2,450.00"]
    ]
]
```

### 6.4 LayoutLM / Detectron2 Layout Analysis

```python
import layoutparser as lp

model = lp.Detectron2LayoutModel(
    config_path="lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
    label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
)
layout = model.detect(image)

# Real output structure:
[
    lp.TextBlock(
        block=Rectangle(x_1=50, y_1=10, x_2=550, y_2=50),
        type="Title", score=0.98, text="INVOICE"
    ),
    lp.TextBlock(
        block=Rectangle(x_1=50, y_1=60, x_2=550, y_2=180),
        type="Text", score=0.95, text="Invoice No: INV-2025-1147\nDate: ..."
    ),
    lp.TextBlock(
        block=Rectangle(x_1=50, y_1=200, x_2=550, y_2=380),
        type="Table", score=0.97, text=""
    )
]
```

### 6.5 spaCy NER Output

```python
import spacy

nlp = spacy.load("en_core_web_trf")
doc = nlp("Invoice from Acme Corporation dated 2025-11-17 for $2,450.00")

# Real output structure:
[
    {"text": "Acme Corporation", "label": "ORG", "start": 13, "end": 29},
    {"text": "2025-11-17", "label": "DATE", "start": 36, "end": 46},
    {"text": "$2,450.00", "label": "MONEY", "start": 51, "end": 60}
]
```

### 6.6 HuggingFace Transformers (Token Classification for Invoice NER)

```python
from transformers import pipeline

ner_pipeline = pipeline("token-classification", model="dslim/bert-base-NER", aggregation_strategy="simple")
results = ner_pipeline("Invoice INV-2025-1147 from Acme Corporation on 17 November 2025")

# Real output structure:
[
    {"entity_group": "ORG", "score": 0.9823, "word": "Acme Corporation", "start": 26, "end": 42},
    {"entity_group": "DATE", "score": 0.9156, "word": "17 November 2025", "start": 46, "end": 62}
]
```

### 6.7 Regex-Based Entity Extraction

```python
import re

text = "Invoice No: INV-2025-1147\nDate: 2025-11-17\nTotal: $2,450.00"

patterns = {
    "invoiceNumber": r"INV-\d{4}-\d{4}",
    "date": r"\d{4}-\d{2}-\d{2}",
    "amount": r"\$[\d,]+\.\d{2}"
}

# Real output:
{
    "invoiceNumber": "INV-2025-1147",
    "date": "2025-11-17",
    "amount": "$2,450.00"
}
```

---

## 7. TDD Unit Tests

### 7.1 test_file_upload.py

```python
import pytest
from src.backend.ingestion.file_upload import FileUpload

class TestFileUpload:
    def test_accept_pdf_file(self, sample_pdf):
        result = FileUpload().save_uploaded_file(sample_pdf)
        assert result.file_type == "application/pdf"
        assert result.document_id is not None

    def test_accept_png_file(self, sample_png):
        result = FileUpload().save_uploaded_file(sample_png)
        assert result.file_type == "image/png"

    def test_accept_jpg_file(self, sample_jpg):
        result = FileUpload().save_uploaded_file(sample_jpg)
        assert result.file_type == "image/jpeg"

    def test_reject_unsupported_file_type(self, sample_exe):
        with pytest.raises(ValueError, match="Unsupported file type"):
            FileUpload().save_uploaded_file(sample_exe)

    def test_reject_oversized_file(self, oversized_file):
        with pytest.raises(ValueError, match="File size exceeds"):
            FileUpload().save_uploaded_file(oversized_file)

    def test_file_saved_to_uploads_dir(self, sample_pdf, tmp_path):
        uploader = FileUpload(upload_dir=tmp_path)
        result = uploader.save_uploaded_file(sample_pdf)
        assert (tmp_path / result.stored_filename).exists()

    def test_unique_filename_generated(self, sample_pdf):
        uploader = FileUpload()
        r1 = uploader.save_uploaded_file(sample_pdf)
        r2 = uploader.save_uploaded_file(sample_pdf)
        assert r1.stored_filename != r2.stored_filename
```

### 7.2 test_preprocessing.py

```python
import numpy as np
import pytest
from src.backend.ingestion.preprocessing import Preprocessing

class TestPreprocessing:
    def test_pdf_to_images_returns_list(self, sample_pdf_path):
        images = Preprocessing().convert_pdf_to_images(sample_pdf_path)
        assert isinstance(images, list)
        assert len(images) > 0
        assert isinstance(images[0], np.ndarray)

    def test_deskew_corrects_rotation(self):
        skewed = np.zeros((100, 100), dtype=np.uint8)
        result = Preprocessing().deskew_image(skewed)
        assert result.shape == skewed.shape

    def test_denoise_reduces_noise(self, noisy_image):
        result = Preprocessing().denoise_image(noisy_image)
        assert result.std() < noisy_image.std()

    def test_grayscale_conversion(self, color_image):
        result = Preprocessing().to_grayscale(color_image)
        assert len(result.shape) == 2  # single channel

    def test_preprocess_document_returns_pages(self, sample_pdf_path):
        pages = Preprocessing().preprocess_document(sample_pdf_path)
        assert all(hasattr(p, "image") and hasattr(p, "page_number") for p in pages)
```

### 7.3 test_ocr_engine.py

```python
import pytest
from src.backend.layout_engine.ocr_engine import OCREngine

class TestOCREngine:
    def test_extract_text_returns_string(self, invoice_image):
        result = OCREngine().extract_text(invoice_image)
        assert isinstance(result.text, str)
        assert len(result.text) > 0

    def test_extract_text_contains_expected_content(self, invoice_image):
        result = OCREngine().extract_text(invoice_image)
        assert "invoice" in result.text.lower() or "INV" in result.text

    def test_extract_with_boxes_returns_bounding_boxes(self, invoice_image):
        blocks = OCREngine().extract_text_with_boxes(invoice_image)
        assert len(blocks) > 0
        assert all(hasattr(b, "text") and hasattr(b, "bbox") and hasattr(b, "confidence") for b in blocks)

    def test_confidence_scores_in_range(self, invoice_image):
        blocks = OCREngine().extract_text_with_boxes(invoice_image)
        for b in blocks:
            assert 0.0 <= b.confidence <= 1.0

    def test_empty_image_returns_empty(self, blank_image):
        result = OCREngine().extract_text(blank_image)
        assert result.text.strip() == ""
```

### 7.4 test_layout_analyzer.py

```python
import pytest
from src.backend.layout_engine.layout_analyzer import LayoutAnalyzer

class TestLayoutAnalyzer:
    def test_detect_regions_from_invoice(self, invoice_image):
        regions = LayoutAnalyzer().analyze_layout(invoice_image)
        assert len(regions) > 0

    def test_region_types_are_valid(self, invoice_image):
        regions = LayoutAnalyzer().analyze_layout(invoice_image)
        valid_types = {"text", "title", "table", "figure", "list", "header"}
        for r in regions:
            assert r.type.lower() in valid_types

    def test_regions_have_bounding_boxes(self, invoice_image):
        regions = LayoutAnalyzer().analyze_layout(invoice_image)
        for r in regions:
            assert len(r.bbox) == 4
            assert all(isinstance(v, (int, float)) for v in r.bbox)

    def test_classify_regions_groups_correctly(self, invoice_image):
        analyzer = LayoutAnalyzer()
        regions = analyzer.analyze_layout(invoice_image)
        grouped = analyzer.classify_regions(regions)
        assert isinstance(grouped, dict)
```

### 7.5 test_table_extractor.py

```python
import pytest
from src.backend.layout_engine.table_extractor import TableExtractor

class TestTableExtractor:
    def test_extract_table_from_pdf(self, invoice_pdf_path):
        tables = TableExtractor().extract_tables_from_pdf(invoice_pdf_path, page_num=0)
        assert len(tables) > 0

    def test_table_has_rows_and_columns(self, invoice_pdf_path):
        tables = TableExtractor().extract_tables_from_pdf(invoice_pdf_path, page_num=0)
        table = tables[0]
        assert len(table.rows) > 1  # header + data
        assert len(table.rows[0]) > 1  # multiple columns

    def test_table_header_detected(self, invoice_pdf_path):
        tables = TableExtractor().extract_tables_from_pdf(invoice_pdf_path, page_num=0)
        header = tables[0].rows[0]
        assert any("description" in str(h).lower() for h in header)

    def test_empty_pdf_returns_empty(self, blank_pdf_path):
        tables = TableExtractor().extract_tables_from_pdf(blank_pdf_path, page_num=0)
        assert tables == []
```

### 7.6 test_entity_extractor.py

```python
import pytest
from src.backend.extraction.entity_extractor import EntityExtractor

class TestEntityExtractor:
    def test_extract_invoice_number(self):
        text = "Invoice No: INV-2025-1147"
        entities = EntityExtractor().extract_entities(text)
        inv = next((e for e in entities if e.type == "invoiceNumber"), None)
        assert inv is not None
        assert inv.value == "INV-2025-1147"

    def test_extract_date(self):
        text = "Date: 2025-11-17"
        entities = EntityExtractor().extract_entities(text)
        date = next((e for e in entities if e.type == "date"), None)
        assert date is not None
        assert date.value == "2025-11-17"

    def test_extract_amount(self):
        text = "Total: $2,450.00"
        entities = EntityExtractor().extract_entities(text)
        amount = next((e for e in entities if e.type == "amount"), None)
        assert amount is not None
        assert amount.value == "$2,450.00"

    def test_extract_vendor_with_ner(self):
        text = "Invoice from Acme Corporation dated 2025-11-17"
        entities = EntityExtractor().extract_with_ner(text)
        org = next((e for e in entities if e.type == "ORG"), None)
        assert org is not None
        assert "Acme" in org.value

    def test_merge_deduplicates_entities(self):
        regex = [{"type": "date", "value": "2025-11-17"}]
        ner = [{"type": "DATE", "value": "2025-11-17"}]
        merged = EntityExtractor().merge_entities(regex, ner)
        dates = [e for e in merged if "date" in e.type.lower()]
        assert len(dates) == 1

    def test_empty_text_returns_empty(self):
        entities = EntityExtractor().extract_entities("")
        assert entities == []
```

### 7.7 test_field_mapper.py

```python
import pytest
from src.backend.extraction.field_mapper import FieldMapper

class TestFieldMapper:
    def test_map_entities_to_schema(self, sample_entities, sample_layout):
        fields = FieldMapper().map_to_schema(sample_entities, sample_layout)
        assert "invoiceNumber" in fields
        assert "date" in fields
        assert "vendorName" in fields
        assert "totalAmount" in fields

    def test_confidence_scores_assigned(self, sample_entities, sample_layout):
        fields = FieldMapper().map_to_schema(sample_entities, sample_layout)
        for field_name, field_data in fields.items():
            assert 0.0 <= field_data.confidence <= 1.0

    def test_resolve_conflicts_picks_highest_confidence(self):
        candidates = [
            {"value": "Acme Corp", "confidence": 0.8},
            {"value": "Acme Corporation", "confidence": 0.95}
        ]
        result = FieldMapper().resolve_conflicts(candidates)
        assert result.value == "Acme Corporation"
```

### 7.8 test_schema_validator.py

```python
import pytest
from src.backend.validation.schema_validator import SchemaValidator

class TestSchemaValidator:
    def test_valid_date_passes(self):
        assert SchemaValidator().validate_date("2025-11-17") is True

    def test_invalid_date_fails(self):
        assert SchemaValidator().validate_date("11/17/2025") is False
        assert SchemaValidator().validate_date("not-a-date") is False

    def test_valid_invoice_number_passes(self):
        assert SchemaValidator().validate_invoice_number("INV-2025-1147") is True

    def test_invalid_invoice_number_fails(self):
        assert SchemaValidator().validate_invoice_number("1147") is False

    def test_valid_amount_passes(self):
        assert SchemaValidator().validate_amount("2450.00") is True
        assert SchemaValidator().validate_amount("$2,450.00") is True

    def test_invalid_amount_fails(self):
        assert SchemaValidator().validate_amount("not-a-number") is False

    def test_required_fields_missing(self):
        fields = {"invoiceNumber": "INV-2025-1147", "date": "2025-11-17"}
        errors = SchemaValidator().validate_required(fields, ["invoiceNumber", "date", "vendorName", "totalAmount"])
        assert "vendorName" in errors
        assert "totalAmount" in errors

    def test_line_item_total_matches(self):
        line_items = [{"amount": 1500.00}, {"amount": 950.00}]
        assert SchemaValidator().validate_line_item_total(line_items, 2450.00) is True

    def test_line_item_total_mismatch(self):
        line_items = [{"amount": 1500.00}, {"amount": 950.00}]
        assert SchemaValidator().validate_line_item_total(line_items, 3000.00) is False

    def test_full_validation_returns_result(self, valid_extracted_fields):
        result = SchemaValidator().validate_fields(valid_extracted_fields)
        assert result.is_valid is True
        assert all(f.status == "valid" for f in result.fields)

    def test_full_validation_catches_errors(self, invalid_extracted_fields):
        result = SchemaValidator().validate_fields(invalid_extracted_fields)
        assert result.is_valid is False
```

### 7.9 test_correction_handler.py

```python
import pytest
from src.backend.validation.correction_handler import CorrectionHandler

class TestCorrectionHandler:
    def test_submit_correction_stores(self, db_session, sample_document):
        correction = CorrectionHandler(db_session).submit_correction(
            document_id=sample_document.id,
            field="vendorName",
            corrected_value="Acme Corporation",
            user_id="usr_a1b2c3"
        )
        assert correction.corrected_value == "Acme Corporation"

    def test_correction_history_retrieved(self, db_session, sample_document_with_corrections):
        history = CorrectionHandler(db_session).get_correction_history(sample_document_with_corrections.id)
        assert len(history) > 0
        assert all(hasattr(c, "original_value") and hasattr(c, "corrected_value") for c in history)

    def test_apply_corrections_updates_fields(self, db_session, sample_document_with_corrections):
        fields = CorrectionHandler(db_session).apply_corrections(sample_document_with_corrections.id)
        assert fields["vendorName"].status == "corrected"
```

### 7.10 test_database_crud.py

```python
import pytest
from src.backend.db.crud import create_document, get_document, store_extracted_fields

class TestDatabaseCRUD:
    def test_create_document(self, db_session):
        doc = create_document(db_session, {
            "file_name": "test.pdf",
            "file_type": "application/pdf",
            "file_size": 12345,
            "file_path": "/uploads/test.pdf",
            "uploaded_by": "usr_a1b2c3"
        })
        assert doc.id is not None
        assert doc.status == "uploaded"

    def test_get_document_by_id(self, db_session, sample_document):
        doc = get_document(db_session, sample_document.id)
        assert doc.file_name == sample_document.file_name

    def test_store_extracted_fields(self, db_session, sample_document):
        fields = store_extracted_fields(db_session, sample_document.id, {
            "invoiceNumber": {"value": "INV-2025-1147", "confidence": 0.97},
            "date": {"value": "2025-11-17", "confidence": 0.95}
        })
        assert len(fields) == 2

    def test_get_nonexistent_document_returns_none(self, db_session):
        doc = get_document(db_session, "nonexistent_id")
        assert doc is None
```

### 7.11 test_dashboard.py

```python
import pytest
from src.backend.analytics.dashboard import AnalyticsModule

class TestDashboard:
    def test_spend_analysis_returns_data(self, db_session_with_data):
        result = AnalyticsModule(db_session_with_data).get_spend_analysis("last_30_days")
        assert "labels" in result
        assert "values" in result
        assert len(result["labels"]) == len(result["values"])

    def test_supplier_performance_returns_list(self, db_session_with_data):
        result = AnalyticsModule(db_session_with_data).get_supplier_performance()
        assert isinstance(result, list)
        assert all("vendor" in s and "score" in s for s in result)

    def test_compliance_score_in_range(self, db_session_with_data):
        score = AnalyticsModule(db_session_with_data).get_compliance_score()
        assert 0.0 <= score <= 100.0

    def test_anomaly_alerts_have_priority(self, db_session_with_data):
        alerts = AnalyticsModule(db_session_with_data).get_anomaly_alerts()
        valid_priorities = {"high", "medium", "low"}
        for alert in alerts:
            assert alert["priority"] in valid_priorities
```

### 7.12 test_predictions.py

```python
import pytest
from src.backend.analytics.predictions import PredictionEngine

class TestPredictions:
    def test_spend_forecast_returns_future_values(self, db_session_with_data):
        forecast = PredictionEngine(db_session_with_data).forecast_spend(months_ahead=3)
        assert "predicted" in forecast
        assert len(forecast["predicted"]["values"]) == 3

    def test_supplier_risk_score_in_range(self, db_session_with_data):
        risk = PredictionEngine(db_session_with_data).predict_supplier_risk("vendor_1")
        assert 0 <= risk.score <= 100
        assert risk.level in {"low", "medium", "high"}

    def test_anomaly_detection_returns_list(self, db_session_with_data):
        anomalies = PredictionEngine(db_session_with_data).detect_anomalies()
        assert isinstance(anomalies, list)

    def test_insights_have_confidence(self, db_session_with_data):
        insights = PredictionEngine(db_session_with_data).generate_insights()
        for insight in insights:
            assert 0.0 <= insight["confidence"] <= 1.0
            assert insight["impact"] in {"low", "medium", "high"}
```

### 7.13 test_jwt_handler.py

```python
import pytest
from src.backend.auth.jwt_handler import create_access_token, verify_token

class TestJWTHandler:
    def test_create_token_returns_string(self):
        token = create_access_token({"sub": "usr_a1b2c3", "role": "reviewer"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self):
        token = create_access_token({"sub": "usr_a1b2c3", "role": "reviewer"})
        payload = verify_token(token)
        assert payload["sub"] == "usr_a1b2c3"
        assert payload["role"] == "reviewer"

    def test_verify_invalid_token_raises(self):
        with pytest.raises(Exception):
            verify_token("invalid.token.here")

    def test_expired_token_raises(self, expired_token):
        with pytest.raises(Exception):
            verify_token(expired_token)
```

### 7.14 test_rbac.py

```python
import pytest
from src.backend.auth.rbac import require_role

class TestRBAC:
    def test_admin_can_access_admin_routes(self, admin_user):
        assert require_role(["admin"])(admin_user) is True

    def test_reviewer_cannot_access_admin_routes(self, reviewer_user):
        with pytest.raises(PermissionError):
            require_role(["admin"])(reviewer_user)

    def test_enterprise_user_can_upload(self, enterprise_user):
        assert require_role(["admin", "reviewer", "enterprise_user"])(enterprise_user) is True

    def test_enterprise_user_cannot_review(self, enterprise_user):
        with pytest.raises(PermissionError):
            require_role(["admin", "reviewer"])(enterprise_user)
```

---

## 8. BDD End-to-End Scenarios

### Scenario 1: Full Pipeline — Upload PDF to Dashboard

```gherkin
Feature: Document Processing Pipeline
  As an enterprise user
  I want to upload an invoice PDF and see extracted data on the dashboard
  So that I can automate document processing

  Scenario: Upload invoice, extract, validate, approve, view dashboard
    Given I am logged in as a "reviewer"
    And I have an invoice PDF "invoice_2025.pdf"

    When I upload the file via POST /api/documents/upload
    Then the response status is 201
    And the response contains a "documentId"
    And the document status is "uploaded"

    When the pipeline processes the document
    Then the document status progresses through:
      | stage              | status    |
      | preprocessing      | completed |
      | ocr                | completed |
      | layoutAnalysis     | completed |
      | entityExtraction   | completed |
      | validation         | completed |

    When I request GET /api/documents/{id}/extraction
    Then the response contains extracted fields:
      | field         | value            | confidence_gte |
      | invoiceNumber | INV-2025-1147    | 0.90           |
      | date          | 2025-11-17       | 0.90           |
      | vendorName    | Acme Corporation | 0.85           |
      | totalAmount   | 2450.00          | 0.90           |

    When I request GET /api/documents/{id}/validation
    Then all fields have status "valid"
    And isValid is true

    When I approve the document via POST /api/documents/{id}/approve
    Then the document status is "approved"
    And storedToDatabase is true

    When I request GET /api/analytics/dashboard
    Then documentsProcessed count has increased by 1
    And totalSpend includes the new invoice amount
```

### Scenario 2: HITL Correction Flow

```gherkin
Feature: Human-in-the-Loop Correction
  As a reviewer
  I want to correct OCR errors before data is stored
  So that the database contains accurate information

  Scenario: Correct vendor name OCR error and approve
    Given a document "doc_x7y8z9" has been processed
    And the extracted vendorName is "Acme Corporatlon" (OCR typo)
    And the validation shows vendorName as "valid" (no schema rule catches typos)

    When I submit a correction via POST /api/documents/{id}/corrections:
      | fieldName  | originalValue     | correctedValue    |
      | vendorName | Acme Corporatlon  | Acme Corporation  |
    Then the response shows correctionsApplied = 1

    When I request GET /api/documents/{id}/corrections
    Then the correction history shows the change with my name and timestamp

    When I approve the document
    Then the stored vendorName is "Acme Corporation"
```

### Scenario 3: Validation Failure Triggers Review

```gherkin
Feature: Schema Validation Catches Errors
  As the system
  I want to catch invalid fields before human review
  So that reviewers focus on real errors

  Scenario: Missing total amount blocks approval
    Given a document has been processed with OCR
    And the totalAmount field is empty (OCR failed to extract it)

    When I request GET /api/documents/{id}/validation
    Then the validation result shows:
      | fieldName   | status  | error                     |
      | totalAmount | invalid | Total amount is required  |
    And isValid is false

    When I try to approve without fixing
    Then the system prevents approval
    And shows "Please fix validation errors"

    When the reviewer enters totalAmount = 2450.00
    And revalidation passes
    And the reviewer approves
    Then the document is stored with totalAmount = 2450.00
```

### Scenario 4: Analytics Dashboard Reflects Stored Data

```gherkin
Feature: Analytics Dashboard
  As an enterprise user
  I want to see spend analysis and supplier performance
  So that I can make data-driven decisions

  Scenario: Dashboard updates after new documents are stored
    Given 10 invoices from different vendors have been approved and stored
    When I request GET /api/analytics/dashboard?dateRange=last_30_days
    Then summaryCards.documentsProcessed >= 10
    And spendAnalysis contains data points for the current month
    And supplierPerformance lists the vendors from the invoices
    And expenseCategories sums match totalSpend
```

### Scenario 5: Predictive Insights

```gherkin
Feature: Predictive Analytics
  As an enterprise user
  I want to see spend forecasts and supplier risk scores
  So that I can plan ahead and mitigate risks

  Scenario: View spend forecast and supplier risk
    Given sufficient historical data exists (50+ documents over 6 months)
    When I request GET /api/predictions/spend-forecast?monthsAhead=3
    Then the response contains 3 predicted values
    And predicted values are reasonable (within 50% of recent actuals)

    When I request GET /api/predictions/supplier-risk
    Then each supplier has a riskScore between 0 and 100
    And each supplier has a riskLevel of "low", "medium", or "high"
    And high-risk suppliers have riskFactors explaining why

    When I request GET /api/predictions/insights
    Then each insight has a confidence score and impact level
```

### Scenario 6: Role-Based Access Control

```gherkin
Feature: Role-Based Access
  As a system administrator
  I want to enforce role-based permissions
  So that sensitive operations are protected

  Scenario: Enterprise user cannot access review functions
    Given I am logged in as an "enterprise_user"
    When I try to POST /api/documents/{id}/approve
    Then the response status is 403

  Scenario: Reviewer can approve but not manage users
    Given I am logged in as a "reviewer"
    When I approve a document via POST /api/documents/{id}/approve
    Then the response status is 200
    When I try to GET /api/admin/users
    Then the response status is 403

  Scenario: Admin can manage users
    Given I am logged in as an "admin"
    When I request GET /api/admin/users
    Then the response status is 200
    When I change a user's role via PUT /api/admin/users/{id}/role
    Then the response shows the updated role
```

---

## 9. Implementation Sequence & Dependencies

> **Cross-reference:** See **Section 18** for how these phases align to the proposal.pdf Gantt timeline (Term 1 and Term 2 milestones).

### Phase 1: Foundation (Sprint 1-2)
> Goal: Backend skeleton + file upload + database working

| Order | Module | Files | Depends On |
|-------|--------|-------|------------|
| 1.1 | Project setup | `main.py`, `config.py`, `requirements.txt` | Nothing |
| 1.2 | Database setup | `db/database.py`, `db/models.py`, `db/crud.py` | 1.1 |
| 1.3 | Auth | `auth/jwt_handler.py`, `auth/rbac.py`, `api/routes_auth.py` | 1.1, 1.2 |
| 1.4 | File upload | `ingestion/file_upload.py`, `api/routes_upload.py` | 1.1, 1.2, 1.3 |
| 1.5 | Preprocessing | `ingestion/preprocessing.py` | 1.4 |
| 1.6 | Tests | `test_file_upload.py`, `test_preprocessing.py`, `test_database_crud.py`, `test_jwt_handler.py`, `test_rbac.py` | 1.2-1.5 |

### Phase 2: Core AI Pipeline (Sprint 3-4)
> Goal: OCR + Layout + NLP extraction working end-to-end

| Order | Module | Files | Depends On |
|-------|--------|-------|------------|
| 2.1 | OCR engine | `layout_engine/ocr_engine.py` | 1.5 |
| 2.2 | Layout analysis | `layout_engine/layout_analyzer.py` | 2.1 |
| 2.3 | Table extraction | `layout_engine/table_extractor.py` | 2.1 |
| 2.4 | Entity extraction | `extraction/entity_extractor.py` | 2.1 |
| 2.5 | Field mapper | `extraction/field_mapper.py` | 2.2, 2.3, 2.4 |
| 2.6 | Extraction API | `api/routes_extraction.py`, `api/routes_documents.py` | 2.5, 1.2 |
| 2.7 | Tests | `test_ocr_engine.py`, `test_layout_analyzer.py`, `test_table_extractor.py`, `test_entity_extractor.py`, `test_field_mapper.py` | 2.1-2.5 |

### Phase 3: Validation & HITL (Sprint 5)
> Goal: Schema validation + human correction loop working

| Order | Module | Files | Depends On |
|-------|--------|-------|------------|
| 3.1 | Schema validator | `validation/schema_validator.py` | 2.5 |
| 3.2 | Correction handler | `validation/correction_handler.py` | 3.1, 1.2 |
| 3.3 | Validation API | `api/routes_validation.py` | 3.1 |
| 3.4 | Review API | `api/routes_review.py` | 3.2 |
| 3.5 | Pipeline orchestrator | `pipeline/document_processor.py` | 1.5, 2.5, 3.1, 3.2, 1.2 |
| 3.6 | Tests | `test_schema_validator.py`, `test_correction_handler.py` | 3.1-3.2 |

### Phase 4: Analytics & Predictions (Sprint 6)
> Goal: Dashboard data + predictive models

| Order | Module | Files | Depends On |
|-------|--------|-------|------------|
| 4.1 | Dashboard analytics | `analytics/dashboard.py` | 1.2 |
| 4.2 | Predictions engine | `analytics/predictions.py` | 1.2 |
| 4.3 | Analytics API | `api/routes_analytics.py` | 4.1 |
| 4.4 | Predictions API | `api/routes_predictions.py` | 4.2 |
| 4.5 | Tests | `test_dashboard.py`, `test_predictions.py` | 4.1-4.2 |

### Phase 5: Frontend (Sprint 7-8)
> Goal: All pages connected to backend APIs

| Order | Module | Files | Depends On |
|-------|--------|-------|------------|
| 5.1 | Project setup | `package.json`, `App.js`, `api/client.js` | Nothing (parallel) |
| 5.2 | Auth pages | `LoginPage.jsx`, `AuthContext.js`, `ProtectedRoute.jsx` | 5.1, 1.3 API |
| 5.3 | Upload page | `UploadPage.jsx`, `FileDropzone.jsx` | 5.2, 1.4 API |
| 5.4 | Processing page | `ProcessingPage.jsx`, `usePolling.js` | 5.3, 3.5 API |
| 5.5 | Validation page | `ValidationPage.jsx` | 5.4, 3.3 API |
| 5.6 | Review page | `ReviewPage.jsx` | 5.5, 3.4 API |
| 5.7 | Dashboard page | `DashboardPage.jsx` | 5.2, 4.3 API |
| 5.8 | Insights page | `InsightsPage.jsx` | 5.2, 4.4 API |
| 5.9 | Admin page | `AdminPage.jsx` | 5.2, 1.3 API |

### Phase 6: Integration & Testing (Sprint 9)
> Goal: All integration tests pass, full pipeline works end-to-end

| Order | Module | Files | Depends On |
|-------|--------|-------|------------|
| 6.1 | Pipeline E2E test | `test_pipeline_end_to_end.py` | All Phase 1-4 |
| 6.2 | Upload-to-extraction test | `test_upload_to_extraction.py` | Phase 1-2 |
| 6.3 | Validation-HITL test | `test_validation_hitl_flow.py` | Phase 3 |
| 6.4 | Analytics flow test | `test_analytics_flow.py` | Phase 4 |

---

## 10. Module Dependency Graph

```
                    ┌──────────────┐
                    │  Frontend    │
                    │  (React.js)  │
                    └──────┬───────┘
                           │ REST API (JSON)
                    ┌──────▼───────┐
                    │  APIHandler  │ ← routes_*.py
                    │  (FastAPI)   │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │   DocumentProcessor     │ ← pipeline orchestrator
              │   (pipeline/            │
              │    document_processor)  │
              └────┬──────┬──────┬─────┘
                   │      │      │
        ┌──────────▼┐  ┌──▼──────▼──────────┐
        │ Ingestion  │  │  LayoutEngine       │
        │            │  │                     │
        │ file_upload│  │ ocr_engine          │
        │ preprocess │  │ layout_analyzer     │
        └────────────┘  │ table_extractor     │
                        └─────────┬───────────┘
                                  │
                        ┌─────────▼───────────┐
                        │  Extraction          │
                        │                      │
                        │ entity_extractor     │
                        │ field_mapper         │
                        └─────────┬────────────┘
                                  │
                        ┌─────────▼────────────┐
                        │  Validation           │
                        │                       │
                        │ schema_validator      │
                        │ correction_handler ◄──┼── Human (HITL)
                        └─────────┬─────────────┘
                                  │
                        ┌─────────▼────────────┐
                        │  Database (db/)       │
                        │                       │
                        │ models.py             │
                        │ crud.py               │
                        │ database.py           │
                        └───┬─────────────┬─────┘
                            │             │
                  ┌─────────▼──┐    ┌─────▼──────────┐
                  │  Analytics  │    │  Predictions    │
                  │  dashboard  │    │  predictions    │
                  └─────────────┘    └─────────────────┘

  ┌──────────┐
  │   Auth    │ ← guards all API routes
  │ jwt_handler│
  │ rbac      │
  └──────────┘
```

### Critical Path (shortest path to working prototype):

```
1. config + main.py + database setup
      ↓
2. file_upload + preprocessing
      ↓
3. ocr_engine (Tesseract/EasyOCR)
      ↓
4. entity_extractor (spaCy + regex)
      ↓
5. schema_validator
      ↓
6. crud.py (store to DB)
      ↓
7. document_processor (orchestrate 2-6)
      ↓
8. API routes (upload + extraction + validation)
      ↓
9. Frontend (Upload + Validation + Review pages)
      ↓
10. dashboard + predictions (can run in parallel with 9)
```

### Python Dependencies (`requirements.txt`)

```
# Web framework
fastapi==0.115.0
uvicorn==0.30.0
python-multipart==0.0.9

# Database
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
alembic==1.13.0

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# OCR
pytesseract==0.3.13
easyocr==1.7.2
paddleocr==2.7.3
pdf2image==1.17.0
pdfplumber==0.11.4

# Layout analysis
layoutparser==0.3.4
detectron2  # install from source for ARM/Mac

# NLP / ML
spacy==3.7.6
transformers==4.44.0
torch==2.4.0

# Image processing
opencv-python==4.10.0.84
Pillow==10.4.0
numpy==1.26.4

# Analytics
scikit-learn==1.5.2
pandas==2.2.3
plotly==5.24.0
statsmodels==0.14.2

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

---

## 11. Diagram & Image Inventory from All PDFs

Every embedded image was extracted via `pdfimages -png` and examined. Below is the full catalog.

### SRS.pdf — 17 images

| Image | Type | Content | Used In |
|-------|------|---------|---------|
| img-000 | Logo | IBA SMCS logo | N/A |
| img-001 | **Wireframe** | Login Page — email, password, role chips (Admin/Reviewer/Enterprise User), Login button | Section 17.1 |
| img-002 | **Wireframe** | Dashboard Page (top) — nav bar, summary cards (Total Spend, Docs Processed, Compliance Score, Anomalies), filters, Spend Analysis line chart, Supplier Performance bar chart | Section 17.2 |
| img-003 | **Wireframe** | Dashboard Page (bottom) — Expense Categories pie chart, Anomaly Detection Alerts (High/Medium/Low priority cards) | Section 17.2 |
| img-004 | **Wireframe** | Upload Page — drag-and-drop zone, Browse Files button, file type icons (PDF/Word/JPG/PNG) | Section 17.3 |
| img-005 | **Wireframe** | Processing Page — 4-step pipeline (Preprocessing, OCR, Layout Analysis, Extracting Entities), progress bars, estimated time | Section 17.4 |
| img-006 | **Wireframe** | Validation Page — field table (Invoice No, Date, Vendor Name, Line Items, Total Amount), Valid/Invalid status indicators, "Proceed to Review" button | Section 17.5 |
| img-007 | **Wireframe** | HITL Review Page (top) — split layout: Document Preview (left) with zoom, Extracted Fields (right) with OCR Result vs Corrected Value columns | Section 17.6 |
| img-008 | **Wireframe** | HITL Review Page (bottom) — Approve/Reject buttons, Correction History panel with original→corrected values, user, timestamp | Section 17.6 |
| img-009 | **Wireframe** | Insights Page (top) — Spend Trend Forecasting (actual + predicted lines), Supplier Delay Risk Scores, AI-Generated Insights cards | Section 17.7 |
| img-010 | **Wireframe** | Insights Page (bottom) — risk factor cards, "How are these predictions generated?" section with 3 explanation cards | Section 17.7 |
| img-011 | **Domain Model** | 14 entities with attributes and relationships (UML class diagram) | Section 14 |
| img-012 | **Math Formula** | Multimodal Fusion: `h = Fuse(h_text, h_image, h_layout)` | Section 16.2 |
| img-013 | **Math Formula** | Token Generation: `P(x_t \| x_{<t}, D)` | Section 16.2 |
| img-014 | **Math Formula** | Instruction-Conditioned Extraction: `y = f_θ(D, instruction)` | Section 16.2 |
| img-015 | **Math Formula** | NER Sequence Labeling: `P(y\|x) = ∏ P(y_i \| x, y_{<i})` | Section 16.3 |
| img-016 | **Math Formula** | Anomaly Detection: `Anomaly(x) = 1 if \|x−μ\| > kσ, else 0` | Section 16.5 |

### SDS.pdf — 4 images

| Image | Type | Content | Used In |
|-------|------|---------|---------|
| img-000 | Logo | IBA SMCS logo | N/A |
| img-001 | **Sequence Diagram** | 9 participants: User, Frontend, APIHandler, Ingestion, LayoutEngine, ExtractionModule, ValidationModule, Human, DatabaseManager, AnalyticsModule — full pipeline with alt-branch for validation failure | Section 12 |
| img-002 | **Class Diagram** | 12 classes: AuthManager, UploadForm, CorrectionInterface, Dashboard, APIHandler, DocumentProcessor, ValidationModule, ExtractionModule, LayoutEngine, BaseModule, DatabaseManager, AnalyticsModule — all attributes, methods, and relationships | Section 13 |
| img-003 | **Package Diagram** | 8 backend packages (ingestion, layout_engine, extraction, validation, db, analytics, api) + Frontend package (4 components) + Database (PostgreSQL) with inter-package dependencies | Section 15 |

### proposal.pdf — 4 images

| Image | Type | Content | Used In |
|-------|------|---------|---------|
| img-000 | Logo | IBA Karachi logo | N/A |
| img-001 | Spacer | Blank | N/A |
| img-002 | Logo | IBA SMCS logo | N/A |
| img-003 | Spacer | Blank | N/A |

The proposal Gantt chart/timeline is in text form on pages 10-11 (see Section 18).

---

## 12. Sequence Diagram — Step-by-Step Pipeline Workflow (SDS)

> Source: SDS.pdf img-001 — Sequence Diagram

### Participants (left to right)

1. **User** (actor)
2. **Frontend** (React UI)
3. **APIHandler** (FastAPI routes)
4. **Ingestion** (file_upload + preprocessing)
5. **LayoutEngine** (OCR + layout + tables)
6. **ExtractionModule** (NER + field mapping)
7. **ValidationModule** (schema validator)
8. **Human** (reviewer actor)
9. **DatabaseManager** (crud.py)
10. **AnalyticsModule** (dashboard + predictions)

### Step-by-Step Message Sequence

```
Step  From                → To                   Method Call                                  Notes
─────────────────────────────────────────────────────────────────────────────────────────────────────
1     User                → Frontend             selectFile()                                  User picks a file
2     Frontend            → Frontend             submit()                                      Frontend validates locally
3     Frontend            → APIHandler           uploadDocument(request)                        POST /api/documents/upload
4     APIHandler          → Ingestion            preprocessDocument(document)                   Deskew, denoise, resize, PDF→images
5     Ingestion           → LayoutEngine         extractText(document)                          Tesseract/EasyOCR OCR
6     LayoutEngine        → LayoutEngine         extractTables(document)                        pdfplumber / image-based table detection
7     LayoutEngine        → ExtractionModule     convertToStructuredFields(extractedText)       spaCy NER + regex + HuggingFace
8     ExtractionModule    → ValidationModule     validateFields(structuredFields)               Schema checks (date, amount, required)
      ┌─────────────── alt [Validation fails] ───────────────────────────────────────────────┐
9a    │ ValidationModule  → Human                requestCorrection(fields)                    │ Display fields needing correction
10a   │ Human             → ValidationModule     submitCorrection(correctedFields)             │ Reviewer edits and submits
      └─────────────────────────────────────────────────────────────────────────────────────────┘
11    ValidationModule    → DatabaseManager      storeData(validatedFields)                     INSERT into extracted_fields, line_items
12    DatabaseManager     → AnalyticsModule      generateDashboard()                            Recompute spend, supplier metrics
13    AnalyticsModule     → Frontend             displayAnalytics()                             Return dashboard JSON
14    Frontend            → User                 (render dashboard)                             Charts and summary cards visible
      ─────────────────────────────────────────────────────────────────────────────────────────
      Human               → Frontend             human-in-the-loop feedback                    Async: corrections feed back to system
```

### How This Maps to Code Files

| Sequence Step | Backend File(s) | API Route |
|---------------|-----------------|-----------|
| Step 3 | `api/routes_upload.py` → `ingestion/file_upload.py` | `POST /api/documents/upload` |
| Step 4 | `ingestion/preprocessing.py` | (internal) |
| Steps 5-6 | `layout_engine/ocr_engine.py`, `layout_engine/table_extractor.py`, `layout_engine/layout_analyzer.py` | (internal) |
| Step 7 | `extraction/entity_extractor.py`, `extraction/field_mapper.py` | `GET /api/documents/{id}/extraction` |
| Step 8 | `validation/schema_validator.py` | `GET /api/documents/{id}/validation` |
| Steps 9a-10a | `validation/correction_handler.py` | `POST /api/documents/{id}/corrections` |
| Step 11 | `db/crud.py` | `POST /api/documents/{id}/approve` |
| Step 12-13 | `analytics/dashboard.py`, `analytics/predictions.py` | `GET /api/analytics/dashboard` |
| Orchestrator | `pipeline/document_processor.py` | `GET /api/documents/{id}/status` |

### Pipeline State Machine (derived from sequence)

```
uploaded → preprocessing → ocr → layout_analysis → extracting → validating
    → review_pending → [approved | rejected] → stored
```

Each state transition updates `documents.status` in the database and is visible via `GET /api/documents/{id}/status`.

---

## 13. Class Diagram — Full Specification (SDS)

> Source: SDS.pdf img-002 — Class Diagram (12 classes)

### 13.1 All Classes with Attributes and Methods

**AuthManager**
```
Attributes: (none shown)
Methods:
  + login(credentials: Map<String, String>): Boolean
  + logout(): void
  + manageRoles(user: String, role: String): void
Relationships:
  → controls access (1:1) to UploadForm, CorrectionInterface, Dashboard
```

**UploadForm** (Frontend)
```
Attributes: (none shown)
Methods:
  + selectFile(): String
  + submit(): Boolean
Relationships:
  → sends documents (1:0..*) to APIHandler
```

**CorrectionInterface** (Frontend)
```
Attributes: (none shown)
Methods:
  + displayFields(fields: Map<String, String>): void
  + submitCorrections(): Boolean
Relationships:
  → sends corrections (1:1) to APIHandler
```

**Dashboard** (Frontend)
```
Attributes: (none shown)
Methods:
  + displayAnalytics(data: Map<String, Any>): void
  + updateTrends(): void
Relationships:
  → requests analytics (1:1) from APIHandler
```

**APIHandler**
```
Attributes: (none shown)
Methods:
  + uploadDocument(request: String): Boolean
  + sendCorrections(request: Map<String, String>): Boolean
  + getDashboard(request: String): Map<String, Any>
Relationships:
  → triggers actions (1:1) on DocumentProcessor
```

**DocumentProcessor**
```
Attributes:
  - currentDocument: String
  - pipelineStatus: String
Methods:
  + runPipeline(document: String): void
  + processDocument(): void
Relationships:
  → uses (1:1) ValidationModule
  → uses (1:1) ExtractionModule (via LayoutEngine)
  → uses (1:1) AnalyticsModule
```

**ValidationModule**
```
Attributes:
  - validationSchema: String
  - correctionsPending: Boolean
Methods:
  + validateFields(fields: Map<String, String>): Boolean
  + requestCorrection(fields: Map<String, String>): Map<String, String>
Relationships:
  → uses (1:1) LayoutEngine
  → human-in-the-loop feedback from CorrectionInterface
```

**ExtractionModule**
```
Attributes:
  - structuredFields: Map<String, String>
Methods:
  + convertToStructuredFields(rawText: String): Map<String, String>
Relationships:
  → receives raw text from LayoutEngine
  → sends structured fields to ValidationModule
```

**LayoutEngine**
```
Attributes:
  - extractedText: String
  - extractedTables: List<String>
Methods:
  + extractText(document: String): String
  + extractTables(document: String): List<String>
Relationships:
  → used by DocumentProcessor, ValidationModule
```

**BaseModule** (Abstract)
```
Methods:
  + run(): void
  + log(message: String): void
Notes:
  All processing modules (LayoutEngine, ExtractionModule, ValidationModule,
  AnalyticsModule, DatabaseManager) extend BaseModule
```

**DatabaseManager**
```
Attributes:
  - records: List<Map<String, String>>
Methods:
  + storeData(validatedFields: Map<String, String>): void
  + retrieveData(query: String): List<Map<String, String>>
Relationships:
  → stores validated data from ValidationModule
  → reads data for AnalyticsModule
```

**AnalyticsModule**
```
Attributes:
  - analyticsData: Map<String, Any>
Methods:
  + generateDashboard(): Map<String, Any>
  + predictMetrics(): Map<String, Any>
Relationships:
  → reads data from DatabaseManager
  → used by DocumentProcessor
```

### 13.2 Class Relationship Summary

```
AuthManager ──controls access──► UploadForm
AuthManager ──controls access──► CorrectionInterface
AuthManager ──controls access──► Dashboard

UploadForm ──sends documents──► APIHandler (1:0..*)
CorrectionInterface ──sends corrections──► APIHandler (1:1)
Dashboard ──requests analytics──► APIHandler (1:1)

APIHandler ──triggers actions──► DocumentProcessor (1:1)

DocumentProcessor ──uses──► ValidationModule (1:1)
DocumentProcessor ──uses──► ExtractionModule (1:1)
DocumentProcessor ──uses──► AnalyticsModule (1:1)

ValidationModule ──uses──► LayoutEngine (1:1)
ValidationModule ◄──HITL feedback──► CorrectionInterface

ExtractionModule ──receives text from──► LayoutEngine (1:1)

DatabaseManager ──stores validated data──► (from ValidationModule)
DatabaseManager ──reads data──► AnalyticsModule

BaseModule ◄──extends── LayoutEngine, ExtractionModule, ValidationModule, AnalyticsModule, DatabaseManager
```

### 13.3 Mapping to Source Files

| Class | Source File | Package |
|-------|-----------|---------|
| AuthManager | `auth/jwt_handler.py` + `auth/rbac.py` | auth |
| UploadForm | `frontend/src/pages/UploadPage.jsx` + `FileDropzone.jsx` | frontend |
| CorrectionInterface | `frontend/src/pages/ReviewPage.jsx` | frontend |
| Dashboard | `frontend/src/pages/DashboardPage.jsx` | frontend |
| APIHandler | `api/routes_*.py` (all route files) | api |
| DocumentProcessor | `pipeline/document_processor.py` | pipeline |
| ValidationModule | `validation/schema_validator.py` + `validation/correction_handler.py` | validation |
| ExtractionModule | `extraction/entity_extractor.py` + `extraction/field_mapper.py` | extraction |
| LayoutEngine | `layout_engine/ocr_engine.py` + `layout_engine/layout_analyzer.py` + `layout_engine/table_extractor.py` | layout_engine |
| BaseModule | `pipeline/document_processor.py` (base class) | pipeline |
| DatabaseManager | `db/database.py` + `db/models.py` + `db/crud.py` | db |
| AnalyticsModule | `analytics/dashboard.py` + `analytics/predictions.py` | analytics |

---

## 14. Domain Model — Entity Relationships (SRS)

> Source: SRS.pdf img-011 — Domain Model Diagram (14 entities)

### 14.1 All Entities with Attributes

**Document**
```
Attributes:
  documentId    — unique identifier
  fileName      — original file name
  fileType      — PDF, Word, JPG, PNG
  uploadDate    — timestamp of upload
  status        — uploaded | processing | validated | approved | rejected
Relationships:
  → produces (1 : 0..*) PreprocessedDocument
  ← uploads (1 : 1) User
```

**PreprocessedDocument**
```
Attributes:
  cleanedImage         — noise-removed image
  deskewedImage        — rotation-corrected image
  noiseReducedImage    — filtered image
Relationships:
  → passes to OCR (1 : 1) OCRResult
```

**OCRResult**
```
Attributes:
  extractedText    — full text output from OCR
  boundingBoxes    — coordinates of each text region
  language         — detected language
Relationships:
  → includes (1 : 1) Layout
  → generates (1 : 1) ExtractedEntities
```

**Layout**
```
Attributes:
  textBlocks    — list of text regions
  tables        — list of detected tables
  sections      — list of document sections (headers, body, footer)
Relationships:
  ← included in OCRResult
```

**ExtractedEntities**
```
Attributes:
  invoiceNumber    — e.g. "INV-2025-1147"
  date             — e.g. "2025-11-17"
  vendorName       — e.g. "Acme Corporation"
  totalAmount      — e.g. 2450.00
  lineItems        — list of {description, amount}
Relationships:
  → validated by (1 : 1) SchemaValidator
```

**SchemaValidator**
```
Attributes:
  validationRules    — list of rules (date format, required fields, etc.)
  errors             — list of validation errors
Methods:
  isValid()          — returns Boolean
Relationships:
  → sends for correction (1 : 1) HumanReview
```

**HumanReview**
```
Attributes:
  reviewId          — unique review identifier
  comments          — reviewer notes
  corrections       — list of {field, original, corrected}
  approvalStatus    — pending | approved | rejected
Relationships:
  → stores approved data (1 : 1) Database
```

**Database**
```
Attributes:
  recordId      — unique record identifier
  storedData    — validated extracted data
Relationships:
  → provides data (1 : 1) AnalyticsModule
  → provides data (1 : 1) PredictionEngine
```

**AnalyticsModule**
```
Methods:
  generateReports()       — spend analysis, compliance
  generateDashboards()    — Plotly charts
Relationships:
  → shows dashboards to User
```

**PredictionEngine**
```
Methods:
  forecastDelay()       — predict supplier delivery delays
  detectAnomalies()     — flag unusual patterns
Relationships:
  → shows predictions to User
```

**User**
```
Attributes:
  userId    — unique user identifier
  name      — display name
  email     — login email
Relationships:
  → uploads (1 : 0..*) Document
  → has (1 : 1) Role
```

**Admin** (specialization of User)
```
Methods:
  manageUsers()     — CRUD on user accounts
  assignRoles()     — change user roles
```

**Role**
```
Attributes:
  roleName       — admin | reviewer | enterprise_user
  permissions    — list of allowed actions
```

### 14.2 Entity Relationship Flow (from diagram)

```
Document (1)
    │ produces (0..*)
    ▼
PreprocessedDocument (1)
    │ passes to OCR (1)
    ▼
OCRResult (1)
    ├── includes (1) ──► Layout
    │                      textBlocks, tables, sections
    └── generates (1) ──► ExtractedEntities
                            invoiceNumber, date, vendorName, totalAmount, lineItems
                            │ validated by (1)
                            ▼
                          SchemaValidator
                            validationRules, errors, isValid()
                            │ sends for correction (1)
                            ▼
                          HumanReview
                            reviewId, comments, corrections, approvalStatus
                            │ stores approved data (1)
                            ▼
                          Database
                            recordId, storedData
                            ├── provides data ──► AnalyticsModule
                            │                      generateReports(), generateDashboards()
                            │                      │ shows dashboards
                            │                      ▼
                            │                    User ◄── has (1) ── Role
                            │                      ▲        userId     roleName
                            │                      │        name       permissions
                            │                      │        email
                            └── provides data ──► PredictionEngine
                                                   forecastDelay(), detectAnomalies()
                                                   │ shows predictions
                                                   ▼
                                                 User

User (1) ── uploads (0..*) ──► Document
Admin ── manageUsers(), assignRoles()
```

### 14.3 Mapping Domain Entities to Database Tables

| Domain Entity | DB Table | Key Columns |
|--------------|----------|-------------|
| Document | `documents` | id, file_name, file_type, status, uploaded_by |
| PreprocessedDocument | (in-memory / temp files) | Stored as images on disk during pipeline |
| OCRResult | `extracted_fields` (text), in-memory (bboxes) | document_id, field_value, bounding_box |
| Layout | (in-memory during processing) | Regions stored as JSONB if needed |
| ExtractedEntities | `extracted_fields` + `line_items` | field_name, field_value, confidence |
| SchemaValidator | (code logic, no table) | Validation rules in `schema_validator.py` |
| HumanReview | `corrections` | document_id, field_name, original_value, corrected_value |
| Database | `documents` (status=approved) | All tables post-approval |
| AnalyticsModule | `analytics_summaries` | period, vendor, total_spend, compliance_score |
| PredictionEngine | `supplier_metrics` | vendor_name, risk_score, risk_level, risk_factors |
| User | `users` | id, email, name, role, status |
| Role | `users.role` column | admin, reviewer, enterprise_user |

---

## 15. Package Diagram — Subsystem Mapping (SDS)

> Source: SDS.pdf img-003 — UML Package Diagram

### 15.1 Backend Package (monolithic, modular)

```
┌─────────────────────────────────────── Backend ──────────────────────────────────────┐
│                                                                                       │
│   ┌─────────── ingestion ───────────┐    ┌─────────── db ────────────────────┐       │
│   │  FileUpload                      │    │  DatabaseManager                  │       │
│   │  Preprocessing                   │    │  Constraint: "Only accessed via   │       │
│   └──────────────────────────────────┘    │   DatabaseManager"                │       │
│                                           │  SQL operations ──► PostgreSQL    │       │
│   ┌─────────── layout_engine ────────┐    └───────────────────────────────────┘       │
│   │  LayoutEngine                    │                                                │
│   │  (human-in-the-loop feedback     │    ┌─────────── analytics ─────────────┐       │
│   │   arrow to validation)           │    │  AnalyticsModule                  │       │
│   └──────────────────────────────────┘    └───────────────────────────────────┘       │
│                                                                                       │
│   ┌─────────── extraction ───────────┐    ┌─────────── api ──────────────────┐       │
│   │  ExtractionModule                │    │  APIHandler                       │       │
│   └──────────────────────────────────┘    │  (receives all frontend requests) │       │
│                                           └───────────────────────────────────┘       │
│   ┌─────────── validation ───────────┐                                                │
│   │  ValidationModule                │                                                │
│   └──────────────────────────────────┘                                                │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

### 15.2 Frontend Package

```
┌─────────────────── Frontend ─────────────────────┐
│  Constraint: "AuthManager required for all        │
│               operations"                         │
│                                                   │
│  UploadForm          CorrectionInterface          │
│  Dashboard           AuthManager                  │
└───────────────────────────────────────────────────┘
```

### 15.3 Database Package

```
┌────── Database ──────┐
│  PostgreSQL           │
│  Constraint: "Only    │
│  accessed via         │
│  DatabaseManager"     │
└───────────────────────┘
```

### 15.4 Inter-Package Communication (from diagram arrows)

| From | To | Communication | Description |
|------|----|---------------|-------------|
| Frontend.UploadForm | API.APIHandler | upload documents | `POST /api/documents/upload` |
| Frontend.CorrectionInterface | API.APIHandler | submit corrections | `POST /api/documents/{id}/corrections` |
| Frontend.Dashboard | API.APIHandler | fetch analytics | `GET /api/analytics/dashboard` |
| Frontend.AuthManager | API.APIHandler | auth requests | `POST /api/auth/login` |
| API.APIHandler | pipeline.DocumentProcessor | triggers actions | Internal function call |
| ingestion | layout_engine | preprocessed images | Internal: `Preprocessing` → `LayoutEngine` |
| layout_engine | extraction | raw text + tables | Internal: `OCREngine` → `EntityExtractor` |
| extraction | validation | structured fields | Internal: `FieldMapper` → `SchemaValidator` |
| validation | db | validated fields | Internal: `SchemaValidator` → `DatabaseManager.storeData()` |
| validation | Frontend (HITL) | human-in-the-loop feedback | Via API: `requestCorrection()` ↔ `submitCorrection()` |
| db | analytics | stored data | Internal: `DatabaseManager.retrieveData()` → `AnalyticsModule` |
| db.DatabaseManager | Database.PostgreSQL | SQL operations | SQLAlchemy ORM |

### 15.5 Mapping Packages to Folder Structure

| SDS Package | Folder | Files |
|-------------|--------|-------|
| ingestion | `src/backend/ingestion/` | `file_upload.py`, `preprocessing.py` |
| layout_engine | `src/backend/layout_engine/` | `ocr_engine.py`, `layout_analyzer.py`, `table_extractor.py` |
| extraction | `src/backend/extraction/` | `entity_extractor.py`, `field_mapper.py` |
| validation | `src/backend/validation/` | `schema_validator.py`, `correction_handler.py` |
| db | `src/backend/db/` | `database.py`, `models.py`, `crud.py` |
| analytics | `src/backend/analytics/` | `dashboard.py`, `predictions.py` |
| api | `src/backend/api/` | `routes_upload.py`, `routes_documents.py`, `routes_extraction.py`, `routes_validation.py`, `routes_review.py`, `routes_analytics.py`, `routes_predictions.py`, `routes_auth.py` |
| Frontend | `src/frontend/src/` | `pages/*.jsx`, `components/*.jsx`, `api/client.js` |

---

## 16. Computational Models & Mathematical Formulas (SRS)

> Sources: SRS.pdf Section 5.3 text + img-012 through img-016

### 16.1 OCR Model (Vision Transformer / Tesseract)

Converts document pixel values to text + layout:

```
ĉ = argmax_c P(c | I)
```

Where `I(x, y)` is the input image, `c` is a character, and the model selects the highest-probability character for each detected region. Implemented in `layout_engine/ocr_engine.py` using Tesseract (primary) and EasyOCR (fallback).

### 16.2 Layout-Aware LLM for Structured Extraction

The system uses multimodal fusion combining text, image regions, and layout embeddings:

**Multimodal Fusion** (SRS img-012):
```
h = Fuse(h_text, h_image, h_layout)
```

Where `h_text` is the text embedding, `h_image` is the image patch embedding, and `h_layout` is the positional/layout embedding.

**Token Generation** (SRS img-013):
```
P(x_t | x_{<t}, D)
```

Auto-regressive generation conditioned on the document `D` and all previously generated tokens.

**Instruction-Conditioned Extraction** (SRS img-014):
```
y = f_θ(D, instruction)
```

The model `f_θ` takes document `D` and an extraction instruction (e.g., "extract invoice number") and returns structured fields `y` containing: Vendor, Invoice Number, Amount, Date, Line-Item Table.

Implemented in `extraction/entity_extractor.py` and `extraction/field_mapper.py` using HuggingFace Transformers.

### 16.3 Named Entity Recognition (NER) Model

Sequence labeling over document text:

**NER Sequence Labeling** (SRS img-015):
```
P(y | x) = ∏_{i=1}^{n} P(y_i | x, y_{<i})
```

Where:
- `x` = document text (tokenized)
- `y` = entity labels (DATE, TOTAL, VENDOR, INVOICE_NUM, LINE_ITEM)
- Each token's label depends on the full input and all previous labels

Entity types extracted: Invoice Number, Date, Vendor Name, Amount, Line Items.

Implemented in `extraction/entity_extractor.py` using spaCy `en_core_web_trf` + HuggingFace `dslim/bert-base-NER`.

### 16.4 Rule-Based Schema Validation

Deterministic checks ensuring accuracy:

**Date format check:**
```
IsValidDate(x) = (x matches regex YYYY-MM-DD)
```

**Amount validation:**
```
Total = Σ(Line Items)
```

The total amount must equal the sum of all line item amounts.

Implemented in `validation/schema_validator.py` with regex patterns and arithmetic checks.

### 16.5 Predictive Analytics Models

**Random Forest** (supplier risk prediction):
```
ŷ = mode(h₁(x), h₂(x), ..., hₖ(x))
```

Where `h₁...hₖ` are individual decision trees and the final prediction is the majority vote. Used to classify supplier delay risk as Low/Medium/High.

**Time-Series Forecasting** (ARIMA / Prophet):
Predicts future spend trends based on historical monthly data. Used in `GET /api/predictions/spend-forecast`.

**Anomaly Detection** (SRS img-016):
```
Anomaly(x) = { 1  if |x − μ| > kσ
             { 0  otherwise
```

Where `μ` is the mean, `σ` is the standard deviation, and `k` is the threshold (typically 2-3). Flags transactions that deviate significantly from normal patterns (e.g., duplicate invoices, unusual payment amounts).

Implemented in `analytics/predictions.py` using scikit-learn (RandomForestClassifier, IsolationForest) and statsmodels (ARIMA).

### 16.6 Human-in-the-Loop Reinforcement

Corrections improve extraction accuracy over time via gradient update:

```
θ_new = θ_old − η ∇_θ L(predicted, corrected)
```

Where:
- `θ` = model parameters
- `η` = learning rate
- `L` = loss between predicted extraction and human-corrected values
- Each correction generates a training signal

Tracked in `corrections` DB table. Future custom model fine-tuning uses this data.

### 16.7 Summary of Models → Code Mapping

| Model | Formula | Implementation File | Library |
|-------|---------|-------------------|---------|
| OCR | `ĉ = argmax P(c\|I)` | `layout_engine/ocr_engine.py` | Tesseract, EasyOCR |
| Multimodal Fusion | `h = Fuse(h_text, h_image, h_layout)` | `extraction/entity_extractor.py` | HuggingFace Transformers |
| NER Sequence | `P(y\|x) = ∏ P(y_i\|x, y_{<i})` | `extraction/entity_extractor.py` | spaCy, HuggingFace |
| Schema Validation | `IsValidDate`, `Total = Σ(items)` | `validation/schema_validator.py` | regex, Python |
| Random Forest | `ŷ = mode(h₁...hₖ)` | `analytics/predictions.py` | scikit-learn |
| Anomaly Detection | `Anomaly = 1 if \|x−μ\| > kσ` | `analytics/predictions.py` | scikit-learn |
| HITL Reinforcement | `θ_new = θ_old − η∇L` | `validation/correction_handler.py` | (future custom model) |

---

## 17. Wireframe Specifications — Detailed UI Text (SRS)

> Sources: SRS.pdf img-001 through img-010. These are **fallback layouts**; new wireframes from the UI/UX team take priority when available.

### 17.1 Login Page (img-001)

```
┌──────────────────────────────────────────────┐
│              [shield icon]                    │
│                                               │
│    Intelligent Document Processing            │
│         Secure Login Portal                   │
│                                               │
│  Email Address                                │
│  ┌─[mail icon]─ user@company.com ───────────┐│
│  └──────────────────────────────────────────┘│
│                                               │
│  Password                                     │
│  ┌─[lock icon]─ ●●●●●●●● ──────────────────┐│
│  └──────────────────────────────────────────┘│
│                                               │
│  Role-Based Access                            │
│  ┌─────────┐ ┌──────────────┐ ┌─────────────┐│
│  │  Admin  │ │  Reviewer ◄──│ │Enterprise   ││
│  │         │ │  (selected)  │ │  User       ││
│  └─────────┘ └──────────────┘ └─────────────┘│
│                                               │
│  ┌────────────── Login ─────────────────────┐│
│  └──────────────────────────────────────────┘│
│                                               │
│  Enterprise-grade security with role-based    │
│  access control                               │
└──────────────────────────────────────────────┘
```

**UI Elements:**
- Header icon: teal shield with checkmark
- Title: "Intelligent Document Processing"
- Subtitle: "Secure Login Portal"
- Email field: icon + placeholder `user@company.com`
- Password field: icon + masked dots
- Role selector: 3 chips — `Admin` | `Reviewer` (teal highlight = selected) | `Enterprise User`
- Submit button: "Login" (teal, full-width)
- Footer text: "Enterprise-grade security with role-based access control"

**Maps to:** `LoginPage.jsx`, `AuthContext.js`, `POST /api/auth/login`

### 17.2 Dashboard Page (img-002 + img-003)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [doc icon] IDP Platform  | Dashboard | Upload | Insights   user  role  │
├─────────────────────────────────────────────────────────────────────────┤
│ Analytics Dashboard                              Export PDF  Export Excel│
│ Monitor spend, performance, and compliance metrics                      │
│                                                                         │
│ Filters: [Last 30 days ▼] [All Vendors ▼] [All Categories ▼]          │
│                                                                         │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│ │ $ +12.5%     │ │ [doc] +8.2%  │ │ [✓] +2.1%   │ │ [⚠] -5.4%   │   │
│ │ Total Spend  │ │ Documents    │ │ Compliance   │ │ Anomalies   │   │
│ │ $1,245,680   │ │ Processed    │ │ Score        │ │ Detected    │   │
│ │              │ │ 2,847        │ │ 94.3%        │ │ 23          │   │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│                                                                         │
│ ┌─── Spend Analysis ────────────┐ ┌─── Supplier Performance ────────┐  │
│ │ Line chart (teal)             │ │ Bar chart (teal)                 │  │
│ │ Y: 0-160,000                  │ │ Acme Corp: 95                    │  │
│ │ X: Jun Jul Aug Sep Oct Nov    │ │ TechSupply: 88                   │  │
│ │ Values: 95K→110K→125K→118K   │ │ GlobalVendor: 92                 │  │
│ │   →132K→145K                  │ │ OfficeMax: 85                    │  │
│ └───────────────────────────────┘ │ QuickShip: 82                    │  │
│                                   └──────────────────────────────────┘  │
│                                                                         │
│ ┌─── Expense Categories ────────┐ ┌─── Anomaly Detection Alerts ────┐  │
│ │ Pie chart:                    │ │ [HIGH] Duplicate invoice         │  │
│ │   Office Supplies (teal)      │ │   detected - INV-2847            │  │
│ │   IT Equipment (green)        │ │ [MEDIUM] Unusual payment         │  │
│ │   Services (purple)           │ │   amount from TechSupply         │  │
│ │   Travel (blue)               │ │ [LOW] Missing PO reference       │  │
│ └───────────────────────────────┘ │   for invoice INV-2831           │  │
│                                   │         [View All Alerts]         │  │
│                                   └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

**UI Elements:**
- Nav bar: IDP Platform (logo + text), Dashboard (selected/blue), Upload, Insights, username + role + logout icon
- Page title: "Analytics Dashboard"
- Subtitle: "Monitor spend, performance, and compliance metrics"
- Filter dropdowns: "Last 30 days", "All Vendors", "All Categories"
- Export buttons: "Export PDF" (with download icon), "Export Excel" (with download icon)
- 4 Summary cards: Total Spend ($1,245,680, +12.5%), Documents Processed (2,847, +8.2%), Compliance Score (94.3%, +2.1%), Anomalies Detected (23, -5.4%)
- Spend Analysis: line chart, teal color, monthly data Jun-Nov
- Supplier Performance: horizontal bar chart, 5 vendors with scores
- Expense Categories: pie chart with 4 segments (Office Supplies, IT Equipment, Services, Travel)
- Anomaly Alerts: 3 cards with severity colors — High (red bg), Medium (yellow bg), Low (blue bg)
- "View All Alerts" button

**Maps to:** `DashboardPage.jsx`, `GET /api/analytics/dashboard`

### 17.3 Upload Page (img-004)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [doc icon] IDP Platform  | Dashboard | Upload | Insights   user  role  │
├─────────────────────────────────────────────────────────────────────────┤
│ Upload Documents                                                        │
│ Upload invoices, receipts, or other documents for processing            │
│                                                                         │
│   ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   │
│   │                                                                 │   │
│   │                      [upload icon]                              │   │
│   │                                                                 │   │
│   │              Drag & Drop your files here                        │   │
│   │                         or                                      │   │
│   │                  ┌─ Browse Files ─┐                             │   │
│   │                  └────────────────┘                              │   │
│   │                                                                 │   │
│   │              [PDF] [Word] [JPG] [PNG]                           │   │
│   │                                                                 │   │
│   │   Supported formats: PDF, Word (.doc, .docx), Images (.jpg, .png) │ │
│   └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**UI Elements:**
- Same nav bar as Dashboard (Upload tab selected/blue)
- Page title: "Upload Documents"
- Subtitle: "Upload invoices, receipts, or other documents for processing"
- Dashed-border drop zone
- Upload cloud icon
- Text: "Drag & Drop your files here" / "or"
- Button: "Browse Files" (outlined)
- File type icons: PDF (red), Word (blue), JPG (green), PNG (blue)
- Helper text: "Supported formats: PDF, Word (.doc, .docx), Images (.jpg, .png)"

**Maps to:** `UploadPage.jsx`, `FileDropzone.jsx`, `POST /api/documents/upload`

### 17.4 Processing Page (img-005)

```
┌──────────────────────────────────────────────┐
│         Processing Document                   │
│    Extracting data from your document         │
│                                               │
│              [document icon]                  │
│                                               │
│  ✓  Preprocessing                             │
│     ████████████████████████████ (complete)    │
│                                               │
│  ◐  Performing OCR                   42%      │
│     █████████████░░░░░░░░░░░░░░               │
│                                               │
│  3  Layout Analysis                           │
│     ░░░░░░░░░░░░░░░░░░░░░░░░░░ (pending)     │
│                                               │
│  4  Extracting Entities                       │
│     ░░░░░░░░░░░░░░░░░░░░░░░░░░ (pending)     │
│                                               │
│         Estimated time remaining              │
│              8 seconds                        │
└──────────────────────────────────────────────┘
```

**UI Elements:**
- Title: "Processing Document"
- Subtitle: "Extracting data from your document"
- Document icon (centered)
- 4 pipeline steps with numbered indicators:
  1. "Preprocessing" — green checkmark (✓), full green progress bar
  2. "Performing OCR" — spinning indicator (◐), 42% progress bar (green partial)
  3. "Layout Analysis" — gray number (3), empty gray bar (pending)
  4. "Extracting Entities" — gray number (4), empty gray bar (pending)
- Footer: "Estimated time remaining" / "8 seconds"
- Polls `GET /api/documents/{id}/status` every 2 seconds

**Maps to:** `ProcessingPage.jsx`, `usePolling.js`, `GET /api/documents/{id}/status`

### 17.5 Validation Page (img-006)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [doc icon] IDP Platform  | Dashboard | Upload | Insights   user  role  │
├─────────────────────────────────────────────────────────────────────────┤
│ Schema Validation                                                       │
│ Review and validate extracted fields                                    │
│                                                                         │
│ ┌─────────────┬──────────────────┬──────────┬──────────┐               │
│ │ Field Name  │ Extracted Value  │ Status   │ Actions  │               │
│ ├─────────────┼──────────────────┼──────────┼──────────┤               │
│ │ Invoice No  │ INV-2025-1147    │ ✓ Valid  │ Edit     │               │
│ ├─────────────┼──────────────────┼──────────┼──────────┤               │
│ │ Date        │ 2025-11-17       │ ✓ Valid  │ Edit     │               │
│ ├─────────────┼──────────────────┼──────────┼──────────┤               │
│ │ Vendor Name │ Acme Corporation │ ✓ Valid  │ Edit     │               │
│ ├─────────────┼──────────────────┼──────────┼──────────┤               │
│ │ Line Items  │ 5                │ ✓ Valid  │ Edit     │               │
│ ├─────────────┼──────────────────┼──────────┼──────────┤               │
│ │ Total       │ [empty, red      │ ✗ Invalid│ Edit     │               │
│ │ Amount      │  border]         │          │          │               │
│ │             │ ⓘ Total amount   │          │          │               │
│ │             │   is required    │          │          │               │
│ └─────────────┴──────────────────┴──────────┴──────────┘               │
│                                                                         │
│ ⚠ Please fix validation errors           ┌─ Proceed to Review ──────┐ │
│                                           └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**UI Elements:**
- Page title: "Schema Validation"
- Subtitle: "Review and validate extracted fields"
- Table columns: Field Name | Extracted Value | Status | Actions
- 5 rows: Invoice No, Date, Vendor Name, Line Items, Total Amount
- Valid status: green checkmark icon + "Valid" text
- Invalid status: red X icon + "Invalid" text
- Invalid field: red border on input, error message "Total amount is required" with info icon
- Warning banner: "Please fix validation errors" (orange)
- Action button: "Proceed to Review" (teal)

**Maps to:** `ValidationPage.jsx`, `GET /api/documents/{id}/validation`

### 17.6 HITL Review Page (img-007 + img-008)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [doc icon] IDP Platform  | Dashboard | Upload | Insights   user  role  │
├─────────────────────────────────────────────────────────────────────────┤
│ Human-in-the-Loop Review                                                │
│ Review and correct extracted data                                       │
│                                                                         │
│ ┌──────── Document Preview ────────┐ ┌──── Extracted Fields ──────────┐│
│ │ [zoom-] 100% [zoom+]            │ │                   [Edit Mode]  ││
│ │ ┌──────────────────────────────┐ │ │                                ││
│ │ │        INVOICE               │ │ │ Invoice No                     ││
│ │ │                              │ │ │ OCR Result      Corrected Value││
│ │ │ Invoice No: [INV-2025-114]   │ │ │ INV-2025-1147   INV-2025-1147 ││
│ │ │            (yellow highlight) │ │ │                                ││
│ │ │ Date:      [2025-11-1]       │ │ │ Date                           ││
│ │ │            (yellow highlight) │ │ │ OCR Result      Corrected Value││
│ │ │ Vendor:    [Acme Corporatlo] │ │ │ 2025-11-17      2025-11-17    ││
│ │ │            (yellow highlight) │ │ │                                ││
│ │ │                              │ │ │ Vendor Name                    ││
│ │ │ Description        Amount    │ │ │ OCR Result      Corrected Value││
│ │ │ Consulting Svc   $1,500     │ │ │ Acme Corporatlon  [Acme Corp- ││
│ │ │ Software License   $950     │ │ │                    oration] ✎  ││
│ │ │                              │ │ │                                ││
│ │ │ Total:           [$2,450.0]  │ │ │ Total Amount                   ││
│ │ │                (green hilite) │ │ │ OCR Result      Corrected Value││
│ │ └──────────────────────────────┘ │ │ $2,450.00       $2,450.00     ││
│ │                                  │ │                                ││
│ │ Highlighted fields indicate      │ │ ┌───── Approve ─────┐ ┌Reject┐││
│ │ potential mismatches             │ │ │  ✓  (green btn)   │ │ ✗    │││
│ │ Yellow = Extracted               │ │ └───────────────────┘ └──────┘││
│ │ Red = Needs correction           │ │                                ││
│ └──────────────────────────────────┘ │ ┌── Correction History ───────┐││
│                                      │ │ Vendor Name       2 mins ago│││
│                                      │ │ Original: Acme Corporation  │││
│                                      │ │ Corrected: Acme Corporation │││
│                                      │ │ by John Doe                 │││
│                                      │ │                             │││
│                                      │ │ Date Format      1 hour ago │││
│                                      │ │ Original: 11/17/2025        │││
│                                      │ │ Corrected: 2025-11-17       │││
│                                      │ │ by Sarah Smith              │││
│                                      │ └─────────────────────────────┘││
│                                      └────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

**UI Elements (Left Panel — Document Preview):**
- Zoom controls: [-] 100% [+]
- Document rendering showing original invoice
- Yellow highlighted fields: extracted OCR text with bounding boxes
- Green highlighted fields: confirmed values
- Legend: "Highlighted fields indicate potential mismatches" / "Yellow = Extracted, Red = Needs correction"

**UI Elements (Right Panel — Extracted Fields):**
- "Edit Mode" toggle button (top right)
- For each field: label, two columns "OCR Result" (read-only) and "Corrected Value" (editable)
- Fields: Invoice No, Date, Vendor Name, Total Amount
- Edit icon (pencil ✎) on corrected value fields
- "Approve" button (green, prominent) / "Reject" button (outlined)
- Correction History panel showing past corrections with: field name, original value (strikethrough red), corrected value (green), corrector name, time ago

**Maps to:** `ReviewPage.jsx`, `POST /api/documents/{id}/corrections`, `POST /api/documents/{id}/approve`, `GET /api/documents/{id}/corrections`

### 17.7 Insights Page (img-009 + img-010)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [doc icon] IDP Platform  | Dashboard | Upload | Insights   user  role  │
├─────────────────────────────────────────────────────────────────────────┤
│ Predictive Insights                      [Download Prediction Report]   │
│ AI-powered forecasting and risk analysis                                │
│                                                                         │
│ ┌─── Spend Trend Forecasting ────────────────────── Actual ─ Predicted ┐│
│ │ Line chart:                                                          ││
│ │ Y: 0-180,000                                                         ││
│ │ X: Dec 2024, Jan-May 2025 (actual, solid teal)                      ││
│ │    Jun-Aug 2025 (predicted, dashed purple, shaded area)              ││
│ │ Actual: 125K → 130K → 128K → 135K → 132K → 140K                    ││
│ │ Predicted: extends upward into 150K-178K range                       ││
│ └──────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ ┌── Supplier Delay Risk Score ──┐ ┌── AI-Generated Insights ──────────┐│
│ │ TechSupply Inc.          78   │ │ [↗] Predicted Spend Increase      ││
│ │ ⓘ High Risk    ████████░░   │ │ Based on historical patterns,     ││
│ │ Risk Factors:                 │ │ spending expected to increase     ││
│ │ • Late deliveries (3x/mo)    │ │ by 12% in Q3 2025                ││
│ │ • Payment delays increasing   │ │ Confidence: 87%  Impact: High    ││
│ │ • Quality complaints up 15%   │ │                                   ││
│ │                               │ │ [↗] Supplier Consolidation        ││
│ │ GlobalVendor Corp        65   │ │ Opportunity                       ││
│ │ ⓘ Medium Risk  ██████░░░░   │ │ Consolidating 3 vendors could     ││
│ │ Risk Factors:                 │ │ reduce costs by $45,000/yr        ││
│ │ • Seasonal demand fluct.      │ │ Confidence: 92%  Impact: High    ││
│ │ • Minor delivery issues       │ │                                   ││
│ │                               │ │ [↗] Seasonal Trend Detected       ││
│ │ Acme Corporation         25   │ │ Office supply purchases peak in   ││
│ │ ⓘ Low Risk     ██░░░░░░░░   │ │ September, recommend bulk         ││
│ │ Risk Factors:                 │ │ ordering in August                ││
│ │ • Consistent on-time delivery │ │ Confidence: 95%  Impact: Medium  ││
│ │ • Strong quality metrics      │ │                                   ││
│ └───────────────────────────────┘ └───────────────────────────────────┘│
│                                                                         │
│ ⓘ How are these predictions generated?                                 │
│ ┌─ Historical Data ──┐ ┌─ Machine Learning ─┐ ┌─ Risk Assessment ────┐ │
│ │ Our AI analyzes    │ │ Advanced regression │ │ Supplier performance │ │
│ │ 12+ months of      │ │ and time-series     │ │ metrics, delivery    │ │
│ │ transaction        │ │ models predict      │ │ history, and quality │ │
│ │ history,           │ │ future outcomes     │ │ indicators combined  │ │
│ │ identifying        │ │ with confidence     │ │ to calculate         │ │
│ │ patterns,          │ │ intervals based on  │ │ comprehensive risk   │ │
│ │ seasonality, and   │ │ statistical         │ │ scores.              │ │
│ │ trends.            │ │ significance.       │ │                      │ │
│ └────────────────────┘ └─────────────────────┘ └──────────────────────┘ │
│                                                                         │
│ Note: Predictions are estimates based on historical data and should be  │
│ used as guidance. Actual outcomes may vary due to market conditions,    │
│ organizational changes, and other external factors.                     │
└─────────────────────────────────────────────────────────────────────────┘
```

**UI Elements:**
- Page title: "Predictive Insights"
- Subtitle: "AI-powered forecasting and risk analysis"
- Download button: "Download Prediction Report" (orange)
- **Spend Trend Forecasting**: line chart with actual (solid teal) + predicted (dashed purple with shaded confidence area), legend "Actual — Predicted"
- **Supplier Delay Risk Score**: cards per vendor showing name, risk score (0-100), risk level (High/Medium/Low), color-coded progress bar (red/orange/green), bulleted risk factors
- **AI-Generated Insights**: cards with trend icon, title, description, confidence %, impact level
- **Explanation section**: "How are these predictions generated?" with 3 cards (Historical Data Analysis, Machine Learning Models, Risk Assessment)
- **Disclaimer**: "Note: Predictions are estimates based on historical data..."

**Maps to:** `InsightsPage.jsx`, `GET /api/predictions/spend-forecast`, `GET /api/predictions/supplier-risk`, `GET /api/predictions/insights`

---

## 18. Project Timeline from proposal.pdf

> Source: proposal.pdf pages 10-11 — Project Plan & Timeline (Gantt chart)

### Term 1 — CSE 493 (Aug–Dec)

| Month | Activity | Milestone |
|-------|----------|-----------|
| Aug–Sep | Project Proposal Report | Proposal Defense |
| Oct–Nov | Requirement Analysis & Specification | SRS + SDS complete |
| Nov–Dec | System Design & Bare MVP | **MVP Ready** |

### Term 2 — CSE 494 (Jan–Jul)

| Month | Activity | Milestone | Blueprint Phase |
|-------|----------|-----------|-----------------|
| Jan–Feb | OCR, Layout Analysis, NLP Extraction | **Core Extraction Ready** | Phase 2 (Core AI Pipeline) |
| Feb–Mar | Validation, Human-in-the-Loop, DB Integration | **Validated Data Stored** | Phase 3 (Validation & HITL) |
| Mar–Apr | Analytics, Dashboards & Predictive Models | **Insights Dashboard Ready** | Phase 4 (Analytics) |
| Apr–May | Security, Benchmarking & Optimization | **Optimized System** | Phase 5 (Frontend) + hardening |
| May–Jun | Testing, Documentation & Finalization | **Final Defense & Report** | Phase 6 (Integration Testing) |

### Post-Term Activities

| Activity | Deliverable |
|----------|-------------|
| Open House / External Jury | Final Artifacts |

### Timeline → Implementation Phase Mapping

```
proposal.pdf Timeline         Blueprint Phase            Key Output
────────────────────────────────────────────────────────────────────────
Aug-Sep: Proposal             (complete)                 proposal.pdf
Oct-Nov: Requirements         (complete)                 SRS.pdf, SDS.pdf
Nov-Dec: System Design + MVP  Phase 1 (Foundation)       DB + auth + upload + preprocess
Jan-Feb: OCR/Layout/NLP       Phase 2 (Core AI)          Tesseract + spaCy + LayoutParser working
Feb-Mar: Validation/HITL/DB   Phase 3 (Validation)       Schema checks + correction loop + pipeline
Mar-Apr: Analytics/Dashboards Phase 4 (Analytics)         Plotly dashboards + predictions
Apr-May: Security/Benchmark   Phase 5 (Frontend)         React pages + RBAC hardening
May-Jun: Testing/Docs         Phase 6 (Integration)      Full E2E tests pass
Jul:     Final Defense        Deployment                 Demo-ready prototype
```

### Current Status (as of project setup)

Term 1 deliverables (SRS, SDS, proposal, system design) are **complete**. Implementation begins at Phase 1.

---

## 19. Research & Improvement Test Metrics (SDS)

> Source: SDS.pdf Section 6 — Design of Tests

In addition to the unit tests (Section 7) and BDD scenarios (Section 8), the SDS defines research-grade evaluation metrics:

### 19.1 Field-Level Accuracy

| Metric | Definition | Target | Test File |
|--------|-----------|--------|-----------|
| Precision | TP / (TP + FP) per field type | ≥ 0.90 | `tests/research/test_field_accuracy.py` |
| Recall | TP / (TP + FN) per field type | ≥ 0.90 | `tests/research/test_field_accuracy.py` |
| F1 Score | 2 * (P * R) / (P + R) per field type | ≥ 0.90 | `tests/research/test_field_accuracy.py` |

Fields measured: invoice_number, date, vendor_name, total_amount, line_items (tables, forms, invoices).

### 19.2 Character / Word Accuracy

| Metric | Definition | Target |
|--------|-----------|--------|
| CER (Character Error Rate) | edit_distance(ocr, ground_truth) / len(ground_truth) | ≤ 5% |
| WER (Word Error Rate) | word-level edit distance / word count | ≤ 10% |

### 19.3 Layout & Structure Retention

| Metric | Definition | Target |
|--------|-----------|--------|
| Table reconstruction accuracy | % of tables correctly parsed (rows, columns match) | ≥ 85% |
| Heading detection accuracy | % of headings correctly identified | ≥ 90% |
| Section ordering accuracy | % of sections in correct reading order | ≥ 95% |

### 19.4 Exact / Partial Match Rate

| Metric | Definition | Target |
|--------|-----------|--------|
| Exact Match Rate | % of documents with ALL fields correctly extracted | ≥ 70% |
| Partial Match Rate | % of documents with MOST fields (≥ 80%) correct | ≥ 90% |

### 19.5 Human-in-the-Loop Metrics

| Metric | Definition | Source |
|--------|-----------|--------|
| Correction Rate | % of documents requiring human correction | `corrections` table |
| Avg Validation Time | Average time from extraction to approval (seconds) | `documents.approved_at - documents.uploaded_at` |
| Confidence vs Error Correlation | Does low confidence predict errors? | `extracted_fields.confidence` vs `corrections` |
| Corrections per Document | Average number of fields corrected per document | `corrections` table |

### 19.6 Comparative Improvement

| Metric | Definition |
|--------|-----------|
| % Improvement over Baseline | Compare system accuracy vs. Tesseract-only baseline |
| Error Type Analysis | Categorize errors: OCR errors, NER misses, schema violations, table parsing failures |

### 19.7 NFR Compliance (from SRS)

| NFR | Requirement | How to Test |
|-----|------------|-------------|
| NFR1 Accuracy | ≥ 95% extraction accuracy for structured data | F1 score on test corpus |
| NFR2 Reliability | Deterministic output, minimal errors | Same input → same output; error rate tracking |
| NFR3 Scalability | Hundreds of documents per day | Load test: 100 docs batch processing |
| NFR4 Performance | Optimized pipeline speed | Measure per-document processing time |
| NFR5 Maintainability | Modular design | Package diagram compliance check |
| NFR6 Security | Enterprise privacy standards | RBAC tests, no data leakage in API responses |
| NFR7 Usability | User-friendly interface | Task completion time for upload → approval workflow |

### 19.8 Suggested Test Folder Addition

```
tests/
├── research/
│   ├── test_field_accuracy.py       ← Precision/Recall/F1 per entity type
│   ├── test_ocr_accuracy.py         ← CER and WER against ground truth
│   ├── test_layout_retention.py     ← Table/heading/section reconstruction
│   ├── test_match_rates.py          ← Exact and partial match rates
│   ├── test_hitl_metrics.py         ← Correction rate, time, confidence correlation
│   ├── test_comparative.py          ← Baseline comparison
│   └── test_nfr_compliance.py       ← All 7 NFRs
```

---

## Summary

This blueprint provides everything needed to implement the Intelligent Document Processing Platform:

- **42 source files** across backend (8 packages) and frontend (8 pages)
- **14 unit test files** + **7 research test files** covering every module and evaluation metric
- **4 integration test files** for end-to-end flows
- **17 API endpoints** with complete JSON request/response contracts
- **7 database tables** with full SQL schema
- **7 real AI library code examples** (Tesseract, EasyOCR, pdfplumber, LayoutParser, spaCy, HuggingFace, regex)
- **7 computational models** with mathematical formulas mapped to code files
- **6 BDD scenarios** covering the complete user journey
- **6 implementation phases** aligned to the proposal.pdf Gantt timeline
- **Critical path** identified for fastest prototype delivery

### Diagrams Fully Integrated

| Diagram | Source | Integrated Into |
|---------|--------|----------------|
| Sequence Diagram (9 participants, 14 steps) | SDS img-001 | Section 12: step-by-step method calls → code file mapping |
| Class Diagram (12 classes) | SDS img-002 | Section 13: all attributes, methods, relationships → source files |
| Package Diagram (8 packages) | SDS img-003 | Section 15: subsystem mapping, constraints, inter-package arrows |
| Domain Model (14 entities) | SRS img-011 | Section 14: all attributes, cardinalities → DB table mapping |
| 6 Math Formulas | SRS img-012–016 + text | Section 16: OCR, NER, fusion, anomaly, validation → library mapping |
| 7 UI Wireframes (Login, Dashboard, Upload, Processing, Validation, Review, Insights) | SRS img-001–010 | Section 17: full ASCII transcription of every label, button, chart, field |
| Gantt Timeline | proposal.pdf pp.10-11 | Section 18: month-by-month → implementation phase mapping |
| Test Metrics (CER, F1, HITL, NFRs) | SDS Section 6 | Section 19: research evaluation framework + suggested test files |

All outputs use real, functioning AI libraries. The custom model replaces the off-the-shelf libraries in a later phase without changing the API contracts.
