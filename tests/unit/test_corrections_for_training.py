"""Tests for crud.get_corrected_documents_for_training.

Verifies the BEFORE/AFTER reconstruction matches what we'd want to
feed into the verifier:
  - Documents without corrections are NOT included
  - For each corrected document, before_field_map has the model's
    original (wrong) value for corrected fields
  - For each corrected document, after_field_map has the human's
    corrected value (which is what's currently in extracted_fields)
  - Multiple corrections on the same field — earliest wins for "before"
"""

from __future__ import annotations

import time

from src.backend.db.crud import (
    create_correction,
    create_document,
    create_user,
    get_corrected_documents_for_training,
    store_extracted_fields,
    update_field_value,
)


def _seed_doc_with_corrections(db, *, user, field_corrections: dict[str, tuple[str, str]]):
    """Create a doc + extracted_fields + corrections.

    `field_corrections` is {field_name: (model_original, human_corrected)}.
    Mirrors production behaviour: the row's field_value ends up at the
    CORRECTED value, while the correction row preserves the model's
    ORIGINAL value.
    """
    doc = create_document(
        db,
        filename="x.pdf",
        original_filename="x.pdf",
        file_type="application/pdf",
        file_size=1024,
        uploaded_by=user.id,
    )
    fields = store_extracted_fields(
        db,
        doc.id,
        [
            {"field_name": "invoice_number", "field_value": "INV-1", "confidence": 0.9},
            {"field_name": "vendor_name", "field_value": "Acme", "confidence": 0.9},
            {"field_name": "total_amount", "field_value": "100.00", "confidence": 0.9},
        ],
    )
    name_to_field = {f.field_name: f for f in fields}

    for field_name, (model_value, corrected_value) in field_corrections.items():
        field = name_to_field[field_name]
        create_correction(
            db,
            document_id=doc.id,
            field_id=field.id,
            original_value=model_value,
            corrected_value=corrected_value,
            reviewed_by=user.id,
        )
        update_field_value(db, field.id, corrected_value)
    return doc


def test_returns_empty_when_no_corrections(db_session):
    user = create_user(
        db_session, email="r@x.com", password="x123pass", name="R", role="reviewer"
    )
    create_document(
        db_session,
        filename="clean.pdf",
        original_filename="clean.pdf",
        file_type="application/pdf",
        file_size=10,
        uploaded_by=user.id,
    )
    out = get_corrected_documents_for_training(db_session)
    assert out == []


def test_includes_only_docs_with_corrections(db_session):
    user = create_user(
        db_session, email="r2@x.com", password="x123pass", name="R", role="reviewer"
    )
    # Doc A: has corrections
    _seed_doc_with_corrections(
        db_session,
        user=user,
        field_corrections={"vendor_name": ("Acmme", "Acme Corp")},
    )
    # Doc B: no corrections
    create_document(
        db_session,
        filename="other.pdf",
        original_filename="other.pdf",
        file_type="application/pdf",
        file_size=10,
        uploaded_by=user.id,
    )
    out = get_corrected_documents_for_training(db_session)
    assert len(out) == 1


def test_before_after_maps_capture_correction(db_session):
    user = create_user(
        db_session, email="r3@x.com", password="x123pass", name="R", role="reviewer"
    )
    _seed_doc_with_corrections(
        db_session,
        user=user,
        field_corrections={
            "vendor_name": ("Acmme", "Acme Corp"),
            "total_amount": ("100.00", "1000.00"),
        },
    )
    out = get_corrected_documents_for_training(db_session)
    assert len(out) == 1
    rec = out[0]

    # BEFORE = what the model produced (the corrections.original_value)
    assert rec["before"]["vendor_name"] == "Acmme"
    assert rec["before"]["total_amount"] == "100.00"
    # Untouched field carries through unchanged on both sides
    assert rec["before"]["invoice_number"] == rec["after"]["invoice_number"]

    # AFTER = the corrected value, which lives in extracted_fields.field_value
    assert rec["after"]["vendor_name"] == "Acme Corp"
    assert rec["after"]["total_amount"] == "1000.00"


def test_earliest_correction_wins_for_before(db_session):
    """If a field is corrected twice, the FIRST original_value is the one
    the model produced. Subsequent corrections built on a human's prior
    value, not the model's."""
    user = create_user(
        db_session, email="r4@x.com", password="x123pass", name="R", role="reviewer"
    )
    doc = create_document(
        db_session,
        filename="two_edits.pdf",
        original_filename="two_edits.pdf",
        file_type="application/pdf",
        file_size=10,
        uploaded_by=user.id,
    )
    fields = store_extracted_fields(
        db_session,
        doc.id,
        [{"field_name": "vendor_name", "field_value": "Acmme", "confidence": 0.9}],
    )
    f = fields[0]
    # First edit: from "Acmme" → "Acme"
    create_correction(
        db_session,
        document_id=doc.id,
        field_id=f.id,
        original_value="Acmme",
        corrected_value="Acme",
        reviewed_by=user.id,
    )
    update_field_value(db_session, f.id, "Acme")
    time.sleep(0.01)
    # Second edit: from "Acme" → "Acme Corp"
    create_correction(
        db_session,
        document_id=doc.id,
        field_id=f.id,
        original_value="Acme",
        corrected_value="Acme Corp",
        reviewed_by=user.id,
    )
    update_field_value(db_session, f.id, "Acme Corp")

    out = get_corrected_documents_for_training(db_session)
    assert len(out) == 1
    # BEFORE should be the very first original_value — "Acmme"
    assert out[0]["before"]["vendor_name"] == "Acmme"
    # AFTER reflects current state — "Acme Corp"
    assert out[0]["after"]["vendor_name"] == "Acme Corp"
