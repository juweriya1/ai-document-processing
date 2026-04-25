"""Tests for synthetic corruption operators.

Each operator must:
  1. Preserve the ExtractedInvoice schema (no missing required fields)
  2. Actually mutate the intended target
  3. Return None when its precondition isn't met (safe to retry another op)
"""

from __future__ import annotations

import random

import pytest

from src.backend.agents.state import ExtractedInvoice, LineItem
from src.backend.verifier import corruption


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
            LineItem(description="Widget A", quantity="2", unit_price="25.00", total="50.00"),
            LineItem(description="Widget B", quantity="2", unit_price="32.50", total="65.00"),
        ],
    )


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


def test_decimal_slip_changes_a_numeric_field(clean_invoice, rng):
    result = corruption.decimal_slip(clean_invoice, rng)
    assert result is not None
    assert result.operator == "decimal_slip"
    assert result.field in ("subtotal", "tax", "total_amount")
    # The mutated field must differ from the original
    new_val = getattr(result.invoice, result.field)
    old_val = getattr(clean_invoice, result.field)
    assert new_val != old_val


def test_digit_drop_shortens_a_numeric_string(clean_invoice, rng):
    result = corruption.digit_drop(clean_invoice, rng)
    assert result is not None
    new_val = getattr(result.invoice, result.field)
    old_val = getattr(clean_invoice, result.field)
    # Digit was dropped → length decreased by 1
    assert len(new_val) == len(old_val) - 1


def test_digit_insert_lengthens_a_numeric_string(clean_invoice, rng):
    result = corruption.digit_insert(clean_invoice, rng)
    assert result is not None
    new_val = getattr(result.invoice, result.field)
    old_val = getattr(clean_invoice, result.field)
    assert len(new_val) == len(old_val) + 1


def test_field_swap_swaps_two_fields(clean_invoice, rng):
    result = corruption.field_swap(clean_invoice, rng)
    assert result is not None
    a, b = result.field.split(",")
    # Each one took the other's value
    assert getattr(result.invoice, a) == getattr(clean_invoice, b)
    assert getattr(result.invoice, b) == getattr(clean_invoice, a)


def test_field_swap_returns_none_when_only_one_populated():
    sparse = ExtractedInvoice(total_amount="100")
    result = corruption.field_swap(sparse, random.Random(1))
    assert result is None


def test_tax_sign_flip_negates_tax(clean_invoice, rng):
    result = corruption.tax_sign_flip(clean_invoice, rng)
    assert result is not None
    assert result.invoice.tax.startswith("-")
    assert result.invoice.subtotal == clean_invoice.subtotal


def test_tax_sign_flip_returns_none_when_no_tax(rng):
    inv = ExtractedInvoice(total_amount="100", subtotal="100", tax=None)
    assert corruption.tax_sign_flip(inv, rng) is None


def test_ocr_confusion_substitutes_one_character(clean_invoice, rng):
    # Try a few seeds — confusion picks a random pair, may not always hit
    found = False
    for seed in range(20):
        result = corruption.ocr_confusion(clean_invoice, random.Random(seed))
        if result is not None:
            found = True
            assert result.invoice != clean_invoice
            break
    assert found, "ocr_confusion should fire on at least one seed"


def test_date_format_swap_swaps_dd_mm(clean_invoice, rng):
    result = corruption.date_format_swap(clean_invoice, rng)
    assert result is not None
    # Original 15/03/2024 → 03/15/2024
    assert result.invoice.date == "03/15/2024"


def test_date_format_swap_returns_none_when_no_date(rng):
    inv = ExtractedInvoice(date=None, total_amount="100")
    assert corruption.date_format_swap(inv, rng) is None


def test_vendor_perturb_changes_vendor_name(clean_invoice, rng):
    result = corruption.vendor_perturb(clean_invoice, rng)
    assert result is not None
    assert result.invoice.vendor_name != clean_invoice.vendor_name
    # Other fields untouched
    assert result.invoice.total_amount == clean_invoice.total_amount


def test_vendor_perturb_returns_none_for_short_vendor(rng):
    inv = ExtractedInvoice(vendor_name="Co", total_amount="100")
    assert corruption.vendor_perturb(inv, rng) is None


def test_line_item_drop_removes_one(clean_invoice, rng):
    result = corruption.line_item_drop(clean_invoice, rng)
    assert result is not None
    assert len(result.invoice.line_items) == len(clean_invoice.line_items) - 1


def test_line_item_drop_returns_none_for_single_item(rng):
    inv = ExtractedInvoice(
        line_items=[LineItem(description="Only", total="50")],
        total_amount="50",
    )
    assert corruption.line_item_drop(inv, rng) is None


def test_line_item_duplicate_adds_one(clean_invoice, rng):
    result = corruption.line_item_duplicate(clean_invoice, rng)
    assert result is not None
    assert len(result.invoice.line_items) == len(clean_invoice.line_items) + 1


def test_quantity_price_skew_breaks_per_line_arithmetic(clean_invoice, rng):
    result = corruption.quantity_price_skew(clean_invoice, rng)
    assert result is not None
    # The mutated line item exists; its qty*price no longer equals total
    idx_str, _ = result.field.split(".")
    idx = int(idx_str.replace("line_items[", "").replace("]", ""))
    li = result.invoice.line_items[idx]
    if li.quantity and li.unit_price and li.total:
        from decimal import Decimal
        expected = Decimal(li.quantity) * Decimal(li.unit_price)
        actual = Decimal(li.total)
        assert abs(expected - actual) > Decimal("0.01")


def test_currency_mismatch_injects_foreign_marker(clean_invoice, rng):
    result = corruption.currency_mismatch(clean_invoice, rng)
    assert result is not None
    new_val = getattr(result.invoice, result.field)
    assert any(marker in new_val for marker in ("$", "€", "£"))


def test_apply_random_returns_some_result(clean_invoice, rng):
    """With a fully-populated invoice, apply_random should always succeed."""
    for seed in range(5):
        result = corruption.apply_random(clean_invoice, random.Random(seed))
        assert result is not None
        assert result.operator in [op.__name__ for op in corruption.ALL_OPERATORS]


def test_apply_random_returns_none_for_empty_invoice():
    """An empty invoice has nothing to corrupt — apply_random should return None gracefully."""
    empty = ExtractedInvoice()
    result = corruption.apply_random(empty, random.Random(1))
    assert result is None


def test_corruption_does_not_mutate_input(clean_invoice, rng):
    """Operators must not modify the input invoice in place — Pydantic
    immutability guarantees this via model_copy. Sanity-check it."""
    snapshot = clean_invoice.model_dump()
    corruption.decimal_slip(clean_invoice, rng)
    corruption.field_swap(clean_invoice, rng)
    corruption.line_item_drop(clean_invoice, rng)
    assert clean_invoice.model_dump() == snapshot
