# Docura — AI Document Intelligence Platform Frontend

A premium, production-grade React frontend for the Intelligent Document Processing platform.

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Set environment variable (optional — defaults to localhost:5000)
cp .env.example .env
# Edit REACT_APP_API_URL if your backend runs on a different port

# 3. Start dev server
npm start
```

The app will open at `http://localhost:3000`.

---

## Project Structure

```
src/
├── App.js                    # Router and top-level layout
├── index.js                  # React entry point
├── styles/
│   └── globals.css           # Design system: CSS variables, utilities, shared components
├── hooks/
│   └── useAuth.js            # AuthContext + useAuth hook (JWT, localStorage)
├── services/
│   └── api.js                # All backend API calls (axios client + interceptors)
├── components/
│   ├── ProtectedRoute.js     # Auth guard for protected pages
│   └── layout/
│       ├── AppLayout.js      # Sidebar + main content shell
│       ├── AppLayout.css
│       ├── Sidebar.js        # Navigation, system status, user profile
│       └── Sidebar.css
│   └── shared/
│       ├── PageHeader.js     # Reusable page title / subtitle / action bar
│       └── PageHeader.css
└── pages/
    ├── LoginPage.js/.css     # Auth — sign in
    ├── RegisterPage.js       # Auth — create account
    ├── Auth.css              # Shared auth styles
    ├── DashboardPage.js/.css # KPI cards, throughput chart, type donut, jobs list, system health
    ├── UploadPage.js/.css    # Drag-drop, document type selector, staged files, pipeline guide
    ├── ProcessingPage.js/.css# Job queue, pipeline stage visualization, log rail
    ├── ValidationPage.js/.css# Extracted field cards, confidence chips, issue flags, approve/reject
    ├── ReviewPage.js/.css    # Human review queue, data panel, audit trail, comment thread
    ├── InsightsPage.js/.css  # Throughput bar, accuracy line, type breakdown
    ├── SettingsPage.js/.css  # Profile, API keys, processing config, notifications
    └── NotFoundPage.js/.css  # 404 screen
```

---

## Backend Compatibility

| Feature | API Endpoint | Notes |
|---|---|---|
| Login | `POST /api/auth/login` | Returns `{ token, user }` |
| Register | `POST /api/auth/register` | Returns `{ token, user }` |
| Auth check | `GET /api/auth/me` | Called on page load to verify token |
| Document list | `GET /api/documents` | |
| Upload | `POST /api/documents/upload` | `multipart/form-data`, field: `file` |
| Start processing | `POST /api/processing/start` | Body: `{ document_id }` |
| Job status | `GET /api/processing/status/:jobId` | |
| Job list | `GET /api/processing/jobs` | |
| Validation list | `GET /api/validation` | |
| Approve validation | `POST /api/validation/:id/approve` | |
| Reject validation | `POST /api/validation/:id/reject` | Body: `{ reason }` |
| Review list | `GET /api/review` | |
| Approve review | `POST /api/review/:id/approve` | Body: `{ notes }` |
| Analytics dashboard | `GET /api/analytics/dashboard` | |

All requests include `Authorization: Bearer <token>` from localStorage.

If the backend returns a 401, the user is automatically logged out and redirected to `/login`.

All pages have **graceful fallback mock data** — the UI renders fully even when the backend is offline, making it safe to demo without a live server.

---

## Design System

The entire visual identity is defined in `src/styles/globals.css` as CSS custom properties:

- **Colors**: Deep navy base (`--bg-base: #080c18`) with electric teal accent (`--accent-primary: #00d4b4`)
- **Typography**: `Syne` (display/headings) + `DM Sans` (body) + `DM Mono` (data/code)
- **Spacing**: `--space-1` through `--space-16` token scale
- **Motion**: `--ease-smooth`, `--ease-spring`, `--duration-fast/base/slow`
- **Shared components**: `.btn`, `.card`, `.badge`, `.form-input`, `.skeleton`, `.pulse-dot`, `.confidence-bar`

---

## Dependencies Added / Changed

| Package | Reason |
|---|---|
| `react-router-dom@6` | Client-side routing (same as original) |
| `axios` | HTTP client with interceptors (same pattern as original) |
| `recharts` | Charts for dashboard and insights |
| `react-dropzone` | Polished drag-and-drop upload |
| `react-hot-toast` | Non-intrusive toast notifications |
| `date-fns` | Date formatting utilities |

All others are standard CRA defaults.

---

## Route Mapping

| Route | Page | Notes |
|---|---|---|
| `/` | → `/dashboard` | Redirect |
| `/login` | LoginPage | Public |
| `/register` | RegisterPage | Public |
| `/dashboard` | DashboardPage | Protected |
| `/upload` | UploadPage | Protected |
| `/processing` | ProcessingPage | Protected |
| `/validation` | ValidationPage | Protected |
| `/review` | ReviewPage | Protected |
| `/insights` | InsightsPage | Protected (previously `/analytics`) |
| `/settings` | SettingsPage | Protected |
| `*` | NotFoundPage | |

> **Note**: The analytics page is now at `/insights` to better reflect the content. If your backend or tests reference `/analytics`, add a `<Route path="/analytics" element={<Navigate to="/insights" replace />} />` in App.js.
