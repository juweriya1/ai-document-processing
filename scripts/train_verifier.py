"""CLI: train a plausibility verifier on clean extractions from the DB.

Usage:
    python scripts/train_verifier.py [--output models/] [--limit 500]
                                     [--negatives 4] [--seed 42]

Side effects:
    - Reads `documents`, `extracted_fields`, `line_items` tables.
    - Writes `models/verifier_v{N}.pkl` (next available version).
    - Prints a summary report (AUROC, AUPRC, F1, ECE, per-operator recall).

Cold-start behavior:
    Refuses to train if fewer than 5 clean documents are available — too
    few to fit a meaningful classifier. The verifier inference path stays
    in skipped mode until enough data accumulates.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make `src.backend` importable when this script is invoked from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.backend.agents.state import ExtractedInvoice, LineItem  # noqa: E402
from src.backend.db.crud import (  # noqa: E402
    get_corrected_documents_for_training,
    get_verified_extractions_for_training,
)
from src.backend.db.database import SessionLocal  # noqa: E402
from src.backend.db.models import (  # noqa: E402
    ExtractedField as ExtractedFieldModel,
    LineItem as LineItemModel,
)
from src.backend.verifier.trainer import TrainConfig, train  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("train_verifier")

_MIN_TRAINING_DOCS = 5


def _build_invoice(field_map: dict, line_items: list) -> ExtractedInvoice:
    return ExtractedInvoice(
        invoice_number=field_map.get("invoice_number"),
        date=field_map.get("date"),
        vendor_name=field_map.get("vendor_name"),
        subtotal=field_map.get("subtotal"),
        tax=field_map.get("tax"),
        total_amount=field_map.get("total_amount"),
        line_items=line_items,
    )


def _load_clean_invoices(limit: int) -> list[ExtractedInvoice]:
    """Materialize ExtractedInvoice objects from the DB rows."""
    db = SessionLocal()
    invoices: list[ExtractedInvoice] = []
    try:
        docs = get_verified_extractions_for_training(db, limit=limit)
        for doc in docs:
            fields = (
                db.query(ExtractedFieldModel)
                .filter(ExtractedFieldModel.document_id == doc.id)
                .all()
            )
            field_map = {f.field_name: f.field_value for f in fields}
            line_rows = (
                db.query(LineItemModel)
                .filter(LineItemModel.document_id == doc.id)
                .all()
            )
            line_items = [
                LineItem(
                    description=li.description,
                    quantity=str(li.quantity) if li.quantity is not None else None,
                    unit_price=str(li.unit_price) if li.unit_price is not None else None,
                    total=str(li.total) if li.total is not None else None,
                )
                for li in line_rows
            ]
            invoices.append(_build_invoice(field_map, line_items))
    finally:
        db.close()
    return invoices


def _load_corrected_pairs(limit: int) -> list[tuple[ExtractedInvoice, int]]:
    """Pull human corrections and emit (invoice, label) pairs.

    For each corrected document we get TWO training examples:
      - the BEFORE extraction (what the model produced) → label 0 (negative)
      - the AFTER  extraction (what the human corrected to) → label 1 (positive)

    These get extra weight in the trainer because they're confirmed
    ground-truth, not synthetic plausibility surrogates.
    """
    db = SessionLocal()
    pairs: list[tuple[ExtractedInvoice, int]] = []
    try:
        records = get_corrected_documents_for_training(db, limit=limit)
        for rec in records:
            line_items = [
                LineItem(
                    description=li.get("description"),
                    quantity=li.get("quantity"),
                    unit_price=li.get("unit_price"),
                    total=li.get("total"),
                )
                for li in rec.get("line_items", [])
            ]
            before_inv = _build_invoice(rec["before"], line_items)
            after_inv = _build_invoice(rec["after"], line_items)
            # Skip if before == after (no meaningful correction was actually
            # made — defensive against schema edge cases).
            if before_inv.model_dump() == after_inv.model_dump():
                continue
            pairs.append((before_inv, 0))
            pairs.append((after_inv, 1))
    finally:
        db.close()
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the plausibility verifier")
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "models",
        help="Directory for verifier_v{N}.pkl artifacts (default: ./models/)",
    )
    parser.add_argument(
        "--limit", type=int, default=500,
        help="Max clean documents to train on (default: 500)",
    )
    parser.add_argument(
        "--negatives", type=int, default=4,
        help="Negative samples per positive (default: 4)",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument(
        "--val-fraction", type=float, default=0.2,
        help="Validation slice (default: 0.2)",
    )
    args = parser.parse_args(argv)

    invoices = _load_clean_invoices(args.limit)
    logger.info("loaded %d clean invoices", len(invoices))

    real_pairs = _load_corrected_pairs(args.limit)
    logger.info(
        "loaded %d real labeled examples from corrections (%d corrected docs)",
        len(real_pairs), len(real_pairs) // 2,
    )

    # We can train on real corrections alone if there are enough — even
    # without clean docs the corrections give us positives (after-edit)
    # and negatives (before-edit). But we still want some clean docs so
    # the verifier sees the unbroken case.
    has_enough = (
        len(invoices) >= _MIN_TRAINING_DOCS
        or len(real_pairs) >= 2 * _MIN_TRAINING_DOCS
    )
    if not has_enough:
        logger.error(
            "need at least %d clean documents OR %d corrected examples to train; "
            "have %d clean and %d corrected. Process more documents through the "
            "pipeline before retraining.",
            _MIN_TRAINING_DOCS,
            2 * _MIN_TRAINING_DOCS,
            len(invoices),
            len(real_pairs),
        )
        return 1

    cfg = TrainConfig(
        negatives_per_positive=args.negatives,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )
    report = train(
        invoices,
        cfg=cfg,
        output_dir=args.output,
        extra_labeled=real_pairs if real_pairs else None,
    )

    logger.info("training complete")
    logger.info("  features            : %d", report.n_features)
    logger.info("  positives           : %d  (%d real, %d synthetic)",
                report.n_positives, report.n_real_positives, report.n_synthetic_positives)
    logger.info("  negatives           : %d  (%d real, %d synthetic)",
                report.n_negatives, report.n_real_negatives, report.n_synthetic_negatives)
    logger.info("  AUROC               : %.4f", report.val_auroc)
    logger.info("  AUPRC               : %.4f", report.val_auprc)
    logger.info("  val F1              : %.4f", report.val_f1)
    logger.info("  threshold (F1-opt)  : %.4f", report.threshold)
    logger.info("  ECE pre-calibration : %.4f", report.pre_calibration_ece)
    logger.info("  ECE post-calibration: %.4f", report.post_calibration_ece)
    if report.per_operator_recall:
        logger.info("  per-operator / per-source recall:")
        for op, recall in sorted(
            report.per_operator_recall.items(), key=lambda kv: kv[1], reverse=True
        ):
            logger.info("    %-22s %.3f", op, recall)
    if report.artifact_path:
        logger.info("  artifact            : %s", report.artifact_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
