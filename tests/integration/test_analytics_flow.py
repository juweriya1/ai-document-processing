import pytest

from tests.integration.conftest import (
    auth_header,
    upload_and_process,
)


class TestAnalyticsDashboard:
    """Scenario 4: Analytics dashboard reflects approved documents"""

    def _approve_doc(self, client, token):
        upload_data, _ = upload_and_process(client, token)
        client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(token),
        )
        return upload_data

    def test_dashboard_empty(self, client, admin_user):
        resp = client.get(
            "/api/analytics/dashboard",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 0
        assert data["total_spend"] == 0

    def test_dashboard_after_approved_doc(self, client, admin_user):
        self._approve_doc(client, admin_user["token"])
        resp = client.get(
            "/api/analytics/dashboard",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] >= 1
        assert data["total_spend"] >= 2450.0

    def test_compliance_all_approved(self, client, admin_user):
        self._approve_doc(client, admin_user["token"])
        self._approve_doc(client, admin_user["token"])
        resp = client.get(
            "/api/analytics/dashboard",
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert data["compliance_score"] == 100.0

    def test_compliance_mixed(self, client, admin_user):
        self._approve_doc(client, admin_user["token"])
        upload_data, _ = upload_and_process(client, admin_user["token"])
        client.post(
            f"/api/documents/{upload_data['id']}/reject",
            headers=auth_header(admin_user["token"]),
            json={"reason": "Bad data"},
        )
        resp = client.get(
            "/api/analytics/dashboard",
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert data["compliance_score"] == 50.0

    def test_spend_by_vendor(self, client, admin_user):
        self._approve_doc(client, admin_user["token"])
        resp = client.get(
            "/api/analytics/spend/by-vendor",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        vendors = resp.json()
        assert len(vendors) >= 1
        acme = next(v for v in vendors if v["vendor_name"] == "Acme Corporation")
        assert acme["total_spend"] >= 2450.0

    def test_spend_by_vendor_aggregates(self, client, admin_user):
        self._approve_doc(client, admin_user["token"])
        self._approve_doc(client, admin_user["token"])
        resp = client.get(
            "/api/analytics/spend/by-vendor",
            headers=auth_header(admin_user["token"]),
        )
        vendors = resp.json()
        acme = next(v for v in vendors if v["vendor_name"] == "Acme Corporation")
        assert acme["total_spend"] >= 4900.0
        assert acme["document_count"] >= 2

    def test_spend_by_month(self, client, admin_user):
        self._approve_doc(client, admin_user["token"])
        resp = client.get(
            "/api/analytics/spend/by-month",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        months = resp.json()
        assert isinstance(months, list)

    def test_dashboard_anomaly_count(self, client, admin_user):
        resp = client.get(
            "/api/analytics/dashboard",
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert isinstance(data["anomaly_count"], int)


class TestPredictiveInsights:
    """Scenario 5: Predictions and anomaly detection"""

    def test_predictions_structure(self, client, admin_user):
        resp = client.get(
            "/api/analytics/predictions",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_scores" in data
        assert "spend_forecast" in data
        assert "anomalies" in data
        assert "insights" in data

    def test_anomalies_empty_small_dataset(self, client, admin_user):
        upload_and_process(client, admin_user["token"])
        resp = client.get(
            "/api/analytics/anomalies",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_suppliers_after_refresh(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(admin_user["token"]),
        )
        client.post(
            "/api/analytics/suppliers/refresh",
            headers=auth_header(admin_user["token"]),
        )
        resp = client.get(
            "/api/analytics/suppliers",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        suppliers = resp.json()
        names = [s["supplier_name"] for s in suppliers]
        assert "Acme Corporation" in names

    def test_supplier_risk_level(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(admin_user["token"]),
        )
        client.post(
            "/api/analytics/suppliers/refresh",
            headers=auth_header(admin_user["token"]),
        )
        suppliers = client.get(
            "/api/analytics/suppliers",
            headers=auth_header(admin_user["token"]),
        ).json()
        for s in suppliers:
            assert s["risk_level"] in ("low", "medium", "high")

    def test_spend_forecast_structure(self, client, admin_user):
        resp = client.get(
            "/api/analytics/predictions",
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert "method" in data["spend_forecast"]
        assert "forecast" in data["spend_forecast"]

    def test_insights_is_list(self, client, admin_user):
        resp = client.get(
            "/api/analytics/predictions",
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert isinstance(data["insights"], list)
