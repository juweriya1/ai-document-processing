"""Tests for deterministic feature extraction.

Features must be:
  1. Deterministic — same input → same output
  2. Stable in length → matches FEATURE_NAMES
  3. Correct on hand-built invoices
  4. Resilient to missing / malformed values (no exceptions)
"""

from __future__ import annotations

from datetime import date

import pytest

from src.backend.agents.state import ExtractedInvoice, LineItem
from src.backend.verifier.features import (
    FEATURE_NAMES,
    N_FEATURES,
    SCHEMA_HASH,
    extract_features,
)


@pytest.fixture
def clean_invoice() -> ExtractedInvoice:
    return ExtractedInvoice(
        invoice_number="INV-2024-001",
        date="15/03/2024",
        vendor_name="Acme Corp",
        subtotal="100.00",
        tax="15.00",
        total_amount="115.00",
        line_items=[
            LineItem(description="A", quantity="2", unit_price="25.00", total="50.00"),
            LineItem(description="B", quantity="2", unit_price="32.50", total="65.00"),
        ],
    )


def test_feature_vector_length_matches_schema(clean_invoice):
    feats = extract_features(clean_invoice)
    assert len(feats.values) == N_FEATURES
    assert N_FEATURES == len(FEATURE_NAMES)


def test_feature_extraction_deterministic(clean_invoice):
    today = date(2024, 5, 1)
    a = extract_features(clean_invoice, today=today)
    b = extract_features(clean_invoice, today=today)
    assert a.values == b.values


def test_clean_invoice_passes_math_residual(clean_invoice):
    feats = extract_features(clean_invoice).to_dict()
    # 100 + 15 == 115 → residual ≈ 0
    assert feats["math_residual_relative"] < 0.01
    assert feats["math_residual_absolute"] < 0.01


def test_broken_math_increases_residual(clean_invoice):
    bad = clean_invoice.model_copy(update={"total_amount": "200.00"})
    feats = extract_features(bad).to_dict()
    assert feats["math_residual_relative"] > 0.4  # off by ~85/200


def test_empty_invoice_does_not_crash():
    feats = extract_features(ExtractedInvoice())
    # All presence flags should be 0
    d = feats.to_dict()
    assert d["has_invoice_number"] == 0.0
    assert d["has_total"] == 0.0
    assert d["n_line_items"] == 0.0


def test_line_item_arithmetic_failrate_zero_for_clean(clean_invoice):
    feats = extract_features(clean_invoice).to_dict()
    # 2 * 25 == 50, 2 * 32.5 == 65 → both pass
    assert feats["line_items_arithmetic_failrate"] == 0.0


def test_line_item_arithmetic_failrate_catches_skew():
    inv = ExtractedInvoice(
        line_items=[
            LineItem(quantity="2", unit_price="25.00", total="50.00"),  # ok
            LineItem(quantity="2", unit_price="100.00", total="50.00"),  # 200 != 50
        ],
    )
    feats = extract_features(inv).to_dict()
    assert feats["line_items_arithmetic_failrate"] == 0.5
    assert feats["line_items_arithmetic_max_dev"] > 0.5  # huge relative diff


def test_log_total_handles_zero_and_missing():
    inv = ExtractedInvoice(total_amount=None)
    feats = extract_features(inv).to_dict()
    assert feats["log_total"] == 0.0  # no NaN, no error


def test_currency_mismatch_detected():
    inv = ExtractedInvoice(
        subtotal="$100",
        tax="€15",
        total_amount="$115",
    )
    feats = extract_features(inv).to_dict()
    # Two distinct currency markers
    assert feats["currency_marker_count_distinct"] >= 2
    assert feats["currency_marker_consistent"] == 0.0


def test_tax_negative_detected():
    inv = ExtractedInvoice(subtotal="100", tax="-10", total_amount="90")
    feats = extract_features(inv).to_dict()
    assert feats["tax_sign_negative"] == 1.0
    assert feats["negative_amount_present"] == 1.0


def test_date_within_5_years(clean_invoice):
    feats = extract_features(clean_invoice, today=date(2024, 5, 1)).to_dict()
    assert feats["date_parses"] == 1.0
    assert feats["date_within_5_years"] == 1.0


def test_date_outside_5_years_flagged():
    inv = ExtractedInvoice(date="01/01/2010")
    feats = extract_features(inv, today=date(2024, 5, 1)).to_dict()
    assert feats["date_parses"] == 1.0
    assert feats["date_within_5_years"] == 0.0


def test_unparseable_date_zeroed():
    inv = ExtractedInvoice(date="not-a-date")
    feats = extract_features(inv).to_dict()
    assert feats["date_parses"] == 0.0
    assert feats["date_within_5_years"] == 0.0


def test_round_amounts_flag(clean_invoice):
    feats = extract_features(clean_invoice).to_dict()
    # 100.00, 15.00, 115.00 — all round
    assert feats["all_amounts_round"] == 1.0


def test_round_amounts_flag_false_for_fractional():
    inv = ExtractedInvoice(subtotal="100.50", tax="15.00", total_amount="115.50")
    feats = extract_features(inv).to_dict()
    assert feats["all_amounts_round"] == 0.0


def test_ocr_confidence_propagates(clean_invoice):
    feats = extract_features(clean_invoice, ocr_confidence=0.92).to_dict()
    assert feats["ocr_confidence"] == 0.92
    assert feats["ocr_confidence_below_85"] == 0.0


def test_ocr_confidence_below_85_flagged(clean_invoice):
    feats = extract_features(clean_invoice, ocr_confidence=0.7).to_dict()
    assert feats["ocr_confidence_below_85"] == 1.0


def test_schema_hash_stable_across_calls(clean_invoice):
    a = extract_features(clean_invoice)
    b = extract_features(clean_invoice)
    assert a.schema_hash == b.schema_hash == SCHEMA_HASH
    assert len(SCHEMA_HASH) == 16  # 64-bit truncated sha256


def test_western_currency_parses(clean_invoice):
    inv = ExtractedInvoice(
        subtotal="$1,500.00",
        tax="$255.00",
        total_amount="$1,755.00",
    )
    feats = extract_features(inv).to_dict()
    assert feats["math_residual_relative"] < 0.01
    assert feats["log_total"] > 3.0  # log10(1755) ≈ 3.24
