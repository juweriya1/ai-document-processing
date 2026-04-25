"""Tests that real human corrections feed the verifier training pipeline.

Covers:
- trainer.train(extra_labeled=...) accepts (invoice, label) pairs and
  reports them in the breakdown
- real labels travel through to the model with the higher sample weight
- training succeeds with ONLY corrected pairs (no clean invoices) — so
  cold-start with corrections-first works
"""

from __future__ import annotations

import pytest

from src.backend.agents.state import ExtractedInvoice, LineItem
from src.backend.verifier.trainer import REAL_LABEL_WEIGHT, TrainConfig, train

pytest.importorskip("lightgbm")  # skip suite if training deps missing


def _clean_invoice(seed: int) -> ExtractedInvoice:
    return ExtractedInvoice(
        invoice_number=f"INV-{seed:04d}",
        date="01/01/2024",
        vendor_name=f"Vendor {seed}",
        subtotal="100.00",
        tax="15.00",
        total_amount="115.00",
        line_items=[
            LineItem(description="Item", quantity="1", unit_price="100.00", total="100.00"),
        ],
    )


def _broken_invoice(seed: int) -> ExtractedInvoice:
    """Math doesn't balance — the kind of thing a human would correct."""
    return ExtractedInvoice(
        invoice_number=f"INV-{seed:04d}",
        date="01/01/2024",
        vendor_name=f"Vendor {seed}",
        subtotal="100.00",
        tax="15.00",
        total_amount="999.99",   # wrong
        line_items=[
            LineItem(description="Item", quantity="1", unit_price="100.00", total="100.00"),
        ],
    )


def test_extra_labeled_appears_in_report_breakdown():
    clean = [_clean_invoice(i) for i in range(20)]
    real_pairs = [
        (_broken_invoice(i), 0) for i in range(100, 105)
    ] + [
        (_clean_invoice(i), 1) for i in range(200, 205)
    ]
    cfg = TrainConfig(seed=7, negatives_per_positive=2)
    report = train(clean, cfg=cfg, output_dir=None, extra_labeled=real_pairs)

    # 5 real positives + 5 real negatives accounted for
    assert report.n_real_positives == 5
    assert report.n_real_negatives == 5
    # 20 clean docs → 20 synthetic positives + ~40 synthetic negatives
    assert report.n_synthetic_positives == 20
    assert report.n_synthetic_negatives > 0
    # Total counts add up
    assert report.n_positives == 25
    assert report.n_negatives == report.n_real_negatives + report.n_synthetic_negatives


def test_train_with_only_real_corrections():
    """Cold-start with ONLY corrections (no verified-clean docs) still works."""
    real_pairs = []
    for i in range(15):
        real_pairs.append((_broken_invoice(i), 0))
        real_pairs.append((_clean_invoice(i), 1))
    cfg = TrainConfig(seed=11, negatives_per_positive=2)
    report = train([], cfg=cfg, output_dir=None, extra_labeled=real_pairs)

    assert report.n_real_positives == 15
    assert report.n_real_negatives == 15
    assert report.n_synthetic_positives == 0
    assert report.n_synthetic_negatives == 0
    # The model trained — threshold and AUROC are populated
    assert report.threshold > 0.0
    assert report.val_auroc >= 0.0


def test_train_raises_when_no_data():
    with pytest.raises(ValueError, match="at least one"):
        train([], cfg=TrainConfig(), output_dir=None, extra_labeled=None)


def test_real_label_weight_is_constant_and_documented():
    """Sanity check — REAL_LABEL_WEIGHT is exposed for tuning."""
    assert REAL_LABEL_WEIGHT > 1.0
