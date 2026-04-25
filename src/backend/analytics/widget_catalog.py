"""
Approved widget catalog for the Analytics page.

The frontend fetches the catalog filtered to the caller's role, then PUTs a
layout ({"enabled": [...], "order": [...]}) of choices. validate_layout is the
server-side guardrail: it strips any keys the user shouldn't be able to pick.
"""

APPROVED_WIDGETS = [
    # Executive KPIs
    {"key": "kpi_total_spend",       "title": "Total Spend",                  "category": "Finance",    "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "kpi_docs_processed",    "title": "Documents Processed",          "category": "Operations", "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "kpi_avg_trust",         "title": "Avg Trust Score",              "category": "Quality",    "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "kpi_auto_approve_rate", "title": "Auto-Approve Rate",            "category": "Operations", "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "kpi_exceptions",        "title": "Compliance Exceptions",        "category": "Compliance", "default": True,  "roles": ["reviewer", "admin"]},
    {"key": "kpi_high_risk_vendors", "title": "High-Risk Vendors",            "category": "Compliance", "default": True,  "roles": ["reviewer", "admin"]},

    # Charts
    {"key": "chart_spend_vendor",    "title": "Spend by Vendor",              "category": "Finance",    "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "chart_spend_trend",     "title": "Monthly Spend Trend",          "category": "Finance",    "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "chart_spend_forecast",  "title": "Spend Forecast",               "category": "Finance",    "default": False, "roles": ["reviewer", "admin"]},
    {"key": "chart_trust_dist",      "title": "Trust Score Distribution",     "category": "Quality",    "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "chart_priority_mix",    "title": "Review Priority Mix",          "category": "Quality",    "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "chart_validation_fail", "title": "Validation Failure Breakdown", "category": "Quality",    "default": True,  "roles": ["reviewer", "admin"]},
    {"key": "chart_correction_top",  "title": "Top Corrected Fields",         "category": "Quality",    "default": False, "roles": ["reviewer", "admin"]},
    {"key": "chart_ocr_drift",       "title": "OCR Confidence Drift",         "category": "Quality",    "default": False, "roles": ["reviewer", "admin"]},
    {"key": "chart_sla",             "title": "Processing SLA",               "category": "Operations", "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
    {"key": "chart_throughput",      "title": "Daily Throughput",             "category": "Operations", "default": False, "roles": ["enterprise_user", "reviewer", "admin"]},

    # Tables and special
    {"key": "table_flagged",         "title": "Flagged Documents",            "category": "Compliance", "default": True,  "roles": ["reviewer", "admin"]},
    {"key": "grid_vendor_risk",      "title": "Vendor Risk Heatmap",          "category": "Compliance", "default": True,  "roles": ["reviewer", "admin"]},
    {"key": "grid_anomalies",        "title": "Statistical Exceptions",       "category": "Compliance", "default": False, "roles": ["reviewer", "admin"]},
    {"key": "iframe_powerbi",        "title": "Executive BI Dashboard",       "category": "Executive",  "default": True,  "roles": ["reviewer", "admin"]},
    {"key": "explainer_formula",     "title": "How Scoring Works",            "category": "Executive",  "default": True,  "roles": ["enterprise_user", "reviewer", "admin"]},
]


def catalog_for_role(role: str) -> list[dict]:
    return [w for w in APPROVED_WIDGETS if role in w["roles"]]


def default_layout_for_role(role: str) -> dict:
    widgets = catalog_for_role(role)
    enabled = [w["key"] for w in widgets if w["default"]]
    order = [w["key"] for w in widgets]
    return {"enabled": enabled, "order": order}


def validate_layout(enabled: list[str], order: list[str], role: str) -> dict:
    allowed = {w["key"] for w in catalog_for_role(role)}
    clean_enabled = [k for k in (enabled or []) if k in allowed]
    clean_order = [k for k in (order or []) if k in allowed]
    for k in clean_enabled:
        if k not in clean_order:
            clean_order.append(k)
    return {"enabled": clean_enabled, "order": clean_order}
