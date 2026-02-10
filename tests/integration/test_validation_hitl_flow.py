import pytest

from tests.integration.conftest import (
    auth_header,
    upload_and_process,
)


class TestValidationFailureBlocksApproval:
    """Scenario 3: Invalid fields block approval; fix-then-approve works"""

    def _corrupt_field(self, client, token, doc_id, field_name, bad_value):
        """Correct a field to an invalid value, then re-validate to mark it invalid."""
        fields = client.get(
            f"/api/documents/{doc_id}/fields",
            headers=auth_header(token),
        ).json()
        field = next(f for f in fields if f["fieldName"] == field_name)
        client.post(
            f"/api/documents/{doc_id}/corrections",
            headers=auth_header(token),
            json={"fieldId": field["id"], "correctedValue": bad_value},
        )
        client.post(
            f"/api/documents/{doc_id}/validate",
            headers=auth_header(token),
        )
        return field["id"]

    def _fix_field(self, client, token, doc_id, field_id, good_value):
        """Correct a field to a valid value, then re-validate."""
        client.post(
            f"/api/documents/{doc_id}/corrections",
            headers=auth_header(token),
            json={"fieldId": field_id, "correctedValue": good_value},
        )
        client.post(
            f"/api/documents/{doc_id}/validate",
            headers=auth_header(token),
        )

    def test_approve_fails_with_invalid_field(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        doc_id = upload_data["id"]
        self._corrupt_field(client, admin_user["token"], doc_id, "invoice_number", "BAD")
        resp = client.post(
            f"/api/documents/{doc_id}/approve",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_error_mentions_invalid_count(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        doc_id = upload_data["id"]
        self._corrupt_field(client, admin_user["token"], doc_id, "invoice_number", "BAD")
        resp = client.post(
            f"/api/documents/{doc_id}/approve",
            headers=auth_header(admin_user["token"]),
        )
        assert "invalid" in resp.json()["detail"].lower()

    def test_fix_then_approve_succeeds(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        doc_id = upload_data["id"]
        field_id = self._corrupt_field(client, admin_user["token"], doc_id, "invoice_number", "BAD")
        self._fix_field(client, admin_user["token"], doc_id, field_id, "INV-2025-5555")
        resp = client.post(
            f"/api/documents/{doc_id}/approve",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_validation_results_show_invalid(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        doc_id = upload_data["id"]
        self._corrupt_field(client, admin_user["token"], doc_id, "invoice_number", "BAD")
        fields = client.get(
            f"/api/documents/{doc_id}/fields",
            headers=auth_header(admin_user["token"]),
        ).json()
        inv_field = next(f for f in fields if f["fieldName"] == "invoice_number")
        assert inv_field["status"] == "invalid"
        assert inv_field["errorMessage"] is not None

    def test_validation_summary_counts(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        doc_id = upload_data["id"]
        self._corrupt_field(client, admin_user["token"], doc_id, "invoice_number", "BAD")
        resp = client.post(
            f"/api/documents/{doc_id}/validate",
            headers=auth_header(admin_user["token"]),
        )
        summary = resp.json()["summary"]
        assert summary["invalid"] >= 1
        assert summary["valid"] + summary["invalid"] + summary["corrected"] + summary["pending"] == 4

    def test_reject_allowed_with_invalid_fields(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        doc_id = upload_data["id"]
        self._corrupt_field(client, admin_user["token"], doc_id, "invoice_number", "BAD")
        resp = client.post(
            f"/api/documents/{doc_id}/reject",
            headers=auth_header(admin_user["token"]),
            json={"reason": "Too many invalid fields"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_partial_fix_still_blocks(self, client, admin_user):
        upload_data, _ = upload_and_process(client, admin_user["token"])
        doc_id = upload_data["id"]
        field_id_1 = self._corrupt_field(client, admin_user["token"], doc_id, "invoice_number", "BAD")
        self._corrupt_field(client, admin_user["token"], doc_id, "total_amount", "NOTNUM")
        self._fix_field(client, admin_user["token"], doc_id, field_id_1, "INV-2025-5555")
        resp = client.post(
            f"/api/documents/{doc_id}/approve",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_corrected_status_passes_gate(self, client, reviewer_user):
        upload_data, _ = upload_and_process(client, reviewer_user["token"])
        doc_id = upload_data["id"]
        fields = client.get(
            f"/api/documents/{doc_id}/fields",
            headers=auth_header(reviewer_user["token"]),
        ).json()
        field_id = fields[0]["id"]
        client.post(
            f"/api/documents/{doc_id}/corrections",
            headers=auth_header(reviewer_user["token"]),
            json={"fieldId": field_id, "correctedValue": "INV-2025-7777"},
        )
        resp = client.post(
            f"/api/documents/{doc_id}/approve",
            headers=auth_header(reviewer_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
