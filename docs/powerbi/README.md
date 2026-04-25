# Power BI Integration — Executive Dashboard

The Procurement Intelligence analytics page exposes an **Executive BI** tab that
embeds a Power BI report via Publish-to-Web (free tier). This document explains
how to build, publish, and refresh that report.

## Architecture

```
FastAPI backend
  └── /api/bi/invoices.json        ← primary fact table
  └── /api/bi/line-items.json
  └── /api/bi/corrections.json
  └── /api/bi/vendor-risk.json
  └── /api/bi/config               ← returns POWER_BI_PUBLIC_URL to the frontend
         │
         ▼
 Power BI Desktop (.pbix)
         │  File → Publish → My Workspace
         ▼
 Power BI Service
         │  File → Embed report → Publish to web (public) → copy iframe URL
         ▼
 POWER_BI_PUBLIC_URL in backend .env
         │
         ▼
 <PowerBIEmbed /> renders iframe in Executive BI tab
```

All four JSON feeds require a JWT with `reviewer` or `admin` role. Power BI
Service refreshes against these endpoints; neither the report nor the embed
URL carry user-identifiable data beyond vendor names.

## First-time publish flow

### 1. Expose backend publicly

Power BI Service cannot reach `localhost`. Use ngrok:

```bash
ngrok http 8000
# Copy the https URL shown, e.g. https://abc123.ngrok-free.app
```

Keep this tunnel running whenever Power BI refreshes.

### 2. Mint a long-lived JWT for BI

Register a dedicated service account:

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"bi@fyp.local","password":"change-me","name":"BI Service","role":"reviewer"}'

curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bi@fyp.local","password":"change-me"}'
# Copy access_token — do not commit it
```

### 3. Load data in Power BI Desktop

1. Open Power BI Desktop (Windows). On macOS use Parallels or work in the Power
   BI Service browser directly.
2. **Home → Get Data → Web → Advanced**.
3. URL: `https://<ngrok>/api/bi/invoices.json`
4. HTTP request header parameters: `Authorization = Bearer <access_token>`.
5. Click OK → the JSON is parsed into a table → **Load**.
6. Repeat for `/line-items.json`, `/corrections.json`, `/vendor-risk.json`.

### 4. Model relationships

In the **Model** view, create:
- `invoices[document_id]` → 1-to-many → `line-items[document_id]`
- `invoices[document_id]` → 1-to-many → `corrections[document_id]`
- `invoices[vendor_name]` → 1-to-many → `vendor-risk[vendor_name]`

### 5. Build report pages

Minimum for demo:

**Executive Overview** — KPI cards (Total Spend, Docs Processed, Avg Trust,
Auto-Approve Rate), Spend by Vendor clustered bar, Monthly Spend line, Fallback
Tier donut.

**Quality & Risk** — Trust score histogram (bin by 10s), Review Priority
stacked column, Top Corrected Fields bar, Vendor Risk matrix coloured by
`risk_level` (red for High).

**Operations** — Daily Throughput column, Processing SLA gauge against 24h
target, OCR confidence drift line.

**Document Detail** — vendor slicer, invoice card, line-items drill-through.

### 6. Publish and embed

1. **File → Publish → My Workspace**. Requires a free Power BI sign-in.
2. In Power BI Service, open the report.
3. **File → Embed report → Publish to web (public)**.
4. Create embed code and copy the `src=` URL (starts with
   `https://app.powerbi.com/view?r=...`).
5. In backend `.env`:
   ```
   POWER_BI_PUBLIC_URL=https://app.powerbi.com/view?r=...
   POWER_BI_LAST_REFRESH=2026-04-24T12:00:00Z
   ```
6. Restart the backend. The Executive BI tab now renders the iframe.

### 7. Commit the .pbix

After the report is built, save as `docs/powerbi/fyp_dashboard.pbix` and
commit. This lets examiners open and inspect the model themselves.

## Refreshing the data

Free tier does not auto-refresh. To pull fresh rows:

1. Start ngrok again (URL will change — update the data source in Power BI).
2. In Power BI Service → Workspace → Semantic model → **Refresh now**.
3. Update `POWER_BI_LAST_REFRESH` in `.env` if you want the footer to show a
   new timestamp.

For a production deployment, swap Publish-to-Web for an Azure-AD-backed
embedding flow (Power BI Embedded). That is intentionally out of scope for the
FYP — see `docs/ROADMAP.md`.

## Defending this in the viva

> "For executive consumers we embed Power BI Service via Publish-to-Web — a
> read-only public embed refreshed against our BI feed endpoints. For
> operational users we keep sub-second analytics in-app with Recharts against
> the same underlying data. The hybrid gives us enterprise BI tooling without
> Premium licensing; the same data model serves both paths."

## Fallback

If `POWER_BI_PUBLIC_URL` is unset, the Executive BI tab shows a clear
configuration card with the steps above. Nothing breaks, nothing blanks.
