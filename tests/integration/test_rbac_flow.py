import pytest

from tests.integration.conftest import (
    auth_header,
    upload_and_process,
    upload_sample_pdf,
)


class TestEnterpriseUserRBAC:
    """Enterprise users can upload/process/view but cannot validate/correct/approve"""

    def test_can_upload(self, client, enterprise_user):
        data = upload_sample_pdf(client, enterprise_user["token"])
        assert data["id"].startswith("doc_")

    def test_can_process(self, client, enterprise_user):
        upload_data = upload_sample_pdf(client, enterprise_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/process",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_status(self, client, enterprise_user):
        upload_data, _ = upload_and_process(client, enterprise_user["token"])
        resp = client.get(
            f"/api/documents/{upload_data['id']}/status",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_fields(self, client, enterprise_user):
        upload_data, _ = upload_and_process(client, enterprise_user["token"])
        resp = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_dashboard(self, client, enterprise_user):
        resp = client.get(
            "/api/analytics/dashboard",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_spend_by_vendor(self, client, enterprise_user):
        resp = client.get(
            "/api/analytics/spend/by-vendor",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_spend_by_month(self, client, enterprise_user):
        resp = client.get(
            "/api/analytics/spend/by-month",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 200

    def test_cannot_validate(self, client, enterprise_user):
        upload_data, _ = upload_and_process(client, enterprise_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/validate",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 403

    def test_cannot_submit_corrections(self, client, enterprise_user):
        upload_data, _ = upload_and_process(client, enterprise_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(enterprise_user["token"]),
        ).json()
        resp = client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(enterprise_user["token"]),
            json={"fieldId": fields[0]["id"], "correctedValue": "NEW"},
        )
        assert resp.status_code == 403

    def test_cannot_get_corrections(self, client, enterprise_user):
        upload_data, _ = upload_and_process(client, enterprise_user["token"])
        resp = client.get(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 403

    def test_cannot_approve(self, client, enterprise_user):
        upload_data, _ = upload_and_process(client, enterprise_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 403

    def test_cannot_reject(self, client, enterprise_user):
        upload_data, _ = upload_and_process(client, enterprise_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/reject",
            headers=auth_header(enterprise_user["token"]),
            json={"reason": "Bad"},
        )
        assert resp.status_code == 403

    def test_cannot_get_suppliers(self, client, enterprise_user):
        resp = client.get(
            "/api/analytics/suppliers",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 403

    def test_cannot_get_predictions(self, client, enterprise_user):
        resp = client.get(
            "/api/analytics/predictions",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 403

    def test_cannot_get_anomalies(self, client, enterprise_user):
        resp = client.get(
            "/api/analytics/anomalies",
            headers=auth_header(enterprise_user["token"]),
        )
        assert resp.status_code == 403


class TestReviewerRBAC:
    """Reviewers can do everything except refresh suppliers"""

    def test_can_upload(self, client, reviewer_user):
        data = upload_sample_pdf(client, reviewer_user["token"])
        assert data["id"].startswith("doc_")

    def test_can_process(self, client, reviewer_user):
        upload_data = upload_sample_pdf(client, reviewer_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/process",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_validate(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/validate",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_submit_corrections(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        resp = client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": fields[0]["id"], "correctedValue": "INV-2025-9999"},
        )
        assert resp.status_code == 200

    def test_can_get_corrections(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        resp = client.get(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_approve(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_suppliers(self, client, reviewer_user):
        resp = client.get(
            "/api/analytics/suppliers",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_predictions(self, client, reviewer_user):
        resp = client.get(
            "/api/analytics/predictions",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_get_anomalies(self, client, reviewer_user):
        resp = client.get(
            "/api/analytics/anomalies",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200

    def test_cannot_refresh_suppliers(self, client, reviewer_user):
        resp = client.post(
            "/api/analytics/suppliers/refresh",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 403


class TestAdminRBAC:
    """Admins can do everything including refresh suppliers"""

    def test_can_refresh_suppliers(self, client, admin_user):
        resp = client.post(
            "/api/analytics/suppliers/refresh",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_validate(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/validate",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_approve(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

    def test_can_access_all_analytics(self, client, admin_user):
        for endpoint in [
            "/api/analytics/dashboard",
            "/api/analytics/spend/by-vendor",
            "/api/analytics/spend/by-month",
            "/api/analytics/suppliers",
            "/api/analytics/predictions",
            "/api/analytics/anomalies",
        ]:
            resp = client.get(endpoint, headers=auth_header(admin_user["token"]))
            assert resp.status_code == 200, f"Failed for {endpoint}"


class TestUnauthenticatedAccess:
    """Unauthenticated requests get 401"""

    def test_upload_requires_auth(self, client):
        resp = client.post("/api/documents/upload")
        assert resp.status_code == 401

    def test_process_requires_auth(self, client):
        resp = client.post("/api/documents/doc_fake/process")
        assert resp.status_code == 401

    def test_get_fields_requires_auth(self, client):
        resp = client.get("/api/documents/doc_fake/fields")
        assert resp.status_code == 401

    def test_dashboard_requires_auth(self, client):
        resp = client.get("/api/analytics/dashboard")
        assert resp.status_code == 401

    def test_validate_requires_auth(self, client):
        resp = client.post("/api/documents/doc_fake/validate")
        assert resp.status_code == 401

    def test_approve_requires_auth(self, client):
        resp = client.post("/api/documents/doc_fake/approve")
        assert resp.status_code == 401
