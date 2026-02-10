import pytest

from tests.integration.conftest import (
    auth_header,
    process_document,
    upload_and_process,
    upload_sample_pdf,
)


class TestFullPipelineEndToEnd:
    """Scenario 1: Upload → Process → Validate → Approve → Dashboard"""

    def test_upload_creates_document(self, client, admin_user):
        data = upload_sample_pdf(client, admin_user["token"])
        assert data["id"].startswith("doc_")
        assert data["status"] == "uploaded"
        assert data["originalFilename"] == "sample_invoice.pdf"
        assert data["fileType"] == "application/pdf"
        assert data["fileSize"] > 0

    def test_process_extracts_fields_and_items(self, client, admin_user):
        upload_data = upload_sample_pdf(client, admin_user["token"])
        result = process_document(client, admin_user["token"], upload_data["id"])
        assert result["fields_extracted"] == 4
        assert result["line_items_extracted"] == 3
        assert result["status"] == "review_pending"

    def test_status_after_processing(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        resp = client.get(
            f"/api/documents/{upload_data['id']}/status",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "review_pending"
        assert data["processed_at"] is not None

    def test_fields_have_correct_data(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        resp = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        fields = resp.json()
        assert len(fields) == 4
        field_map = {f["fieldName"]: f for f in fields}
        assert field_map["invoice_number"]["fieldValue"] == "INV-2025-0001"
        assert field_map["date"]["fieldValue"] == "2025-01-15"
        assert field_map["vendor_name"]["fieldValue"] == "Acme Corporation"
        assert field_map["total_amount"]["fieldValue"] == "2450.00"
        for f in fields:
            assert f["status"] == "valid"

    def test_validate_all_valid(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/validate",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["all_resolved"] is True
        assert data["summary"]["valid"] == 4

    def test_approve_succeeds(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_full_pipeline_to_dashboard(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(admin_user["token"]),
        )
        resp = client.get(
            "/api/analytics/dashboard",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] >= 1
        assert data["total_spend"] >= 2450.0

    def test_reject_with_reason(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        resp = client.post(
            f"/api/documents/{upload_data['id']}/reject",
            headers=auth_header(admin_user["token"]),
            json={"reason": "Data quality too low"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["reason"] == "Data quality too low"

    def test_cannot_reprocess_approved_doc(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(admin_user["token"]),
        )
        resp = client.post(
            f"/api/documents/{upload_data['id']}/process",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400


class TestHITLCorrectionFlow:
    """Scenario 2: Correct fields via HITL and then approve"""

    def test_submit_correction(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        field_id = fields[0]["id"]

        resp = client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-9999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correctionId"].startswith("cor_")
        assert data["correctedValue"] == "INV-2025-9999"

    def test_field_status_becomes_corrected(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        field_id = fields[0]["id"]

        client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-9999"},
        )

        updated_fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        corrected = next(f for f in updated_fields if f["id"] == field_id)
        assert corrected["status"] == "corrected"
        assert corrected["fieldValue"] == "INV-2025-9999"

    def test_corrections_history(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        field_id = fields[0]["id"]

        client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-9999"},
        )

        resp = client.get(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200
        corrections = resp.json()
        assert len(corrections) == 1

    def test_multiple_corrections_accumulate(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        field_id = fields[0]["id"]

        client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-1111"},
        )
        client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-2222"},
        )

        corrections = client.get(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        assert len(corrections) == 2

    def test_approve_after_correction(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        field_id = fields[0]["id"]

        client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-9999"},
        )

        resp = client.post(
            f"/api/documents/{upload_data['id']}/approve",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_correction_records_reviewer(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        fields = client.get(
            f"/api/documents/{upload_data['id']}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        field_id = fields[0]["id"]

        client.post(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-9999"},
        )

        corrections = client.get(
            f"/api/documents/{upload_data['id']}/corrections",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        assert corrections[0]["reviewed_by"] == reviewer_user["user"]["id"]
