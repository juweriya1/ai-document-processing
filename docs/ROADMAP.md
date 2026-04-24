# Roadmap — Beyond FYP Submission

The FYP submission covers the core agentic IDP pipeline, trust scoring,
vendor risk, widget-configurable analytics, and Power BI integration via
Publish-to-Web. The following items are intentionally deferred to post-FYP
phases; they were scoped out to keep demo-day surface area defensible.

## Detection and heuristics

- **Duplicate-invoice detection.** Near-duplicate invoice number + vendor +
  amount within a rolling window. Requires a deterministic hash layer on top
  of the extraction output; blocked on a curated duplicate-set for evaluation.
- **Fraud heuristics.** Benford's-law amount distribution checks, round-number
  bias, ghost-vendor detection (vendor created same week as first invoice).
  Needs a fraud-review feedback loop before any rule goes live.
- **Document category classification.** Invoice vs PO vs receipt vs contract.
  Current pipeline assumes all inputs are invoices. Category classification
  would gate which field schema the extractor applies.

## Pipeline

- **Per-stage SLA tracking.** Track time in OCR → extraction → validation →
  review separately, surface stage-level bottlenecks. Currently we only
  measure end-to-end (upload → approve) SLA.
- **Per-vendor extraction prompt templates.** High-volume vendors benefit from
  a vendor-specific extractor prompt. Requires a template management UI.
- **Active-learning correction capture.** When a reviewer corrects a field,
  queue the pair for fine-tuning data. Infrastructure exists
  (`ConfidenceCalibrator`); the end-to-end active-learning loop does not.

## BI and reporting

- **Power BI Embedded (Azure AD tenant).** Replace Publish-to-Web with
  app-owns-data embedding for row-level security, user-specific filters, and
  no "public link" footprint. Requires a Power BI Premium capacity or an A-SKU.
- **Scheduled refresh via on-premises data gateway.** Today, refresh is manual
  through Power BI Service. An on-prem gateway would let the `.pbix` refresh
  against the live backend without exposing ngrok.
- **Custom semantic model.** Today's model is direct over JSON feeds. Moving
  to a star schema with a dedicated semantic layer would enable drill-through
  across KPIs without writing new DAX per page.

## Platform

- **Multi-tenant isolation.** User sees only documents uploaded by their
  organization. Currently single-tenant.
- **Webhook notifications.** Emit events (`document.approved`,
  `document.rejected`, `vendor.flagged`) so downstream ERP/AP systems can
  auto-ingest.
- **Audit log UI.** Surface the `corrections` and `users` activity in a
  reviewer-facing audit page. Data is captured; UI is not.

## Known gaps called out in the FYP viva

- `ConfidenceCalibrator` is present but not called from the pipeline. Wiring
  it in requires evaluation data for the calibration fit.
- The `compliance_score` metric is currently `1 - (docs_with_invalid_fields /
  total_docs)`. A more complete definition would include required-field
  coverage, per-line-item reconciliation, and vendor compliance rules.
- Document ingestion assumes PDF. Image-only ingestion works but has not been
  benchmarked on the CORD/SROIE evaluation sets.

---

These items are tracked here rather than in commit messages or branch names to
keep the FYP scope defensible and the post-FYP plan legible.
