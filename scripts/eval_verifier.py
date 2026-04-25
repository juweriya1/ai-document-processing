"""CLI: evaluate a trained verifier against held-out synthetic + real corrections.

Usage:
    python scripts/eval_verifier.py [--model models/verifier_v1.pkl]
                                    [--n-corrupt 5]
                                    [--corrections-holdout 50]

Reports:
    - Synthetic AUROC, AUPRC, F1 on held-out corrupted/clean pairs.
    - Reliability diagram bins (ascii) — calibration sanity check.
    - Real-corrections precision/recall: of the documents the model flags
      as low-plausibility, what fraction actually had human corrections?

Honest evaluation: the synthetic numbers reflect how well the verifier
recognizes the corruption operators it was trained on. The corrections
holdout is the real-world test — it's the number that matters for
production decisions and for the paper.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.backend.agents.state import ExtractedInvoice, LineItem  # noqa: E402
from src.backend.db.database import SessionLocal  # noqa: E402
from src.backend.db.models import (  # noqa: E402
    Correction as CorrectionModel,
    Document as DocumentModel,
    ExtractedField as ExtractedFieldModel,
    LineItem as LineItemModel,
)
from src.backend.verifier import corruption  # noqa: E402
from src.backend.verifier.predictor import PlausibilityVerifier  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("eval_verifier")


def _doc_to_invoice(db, doc_id: str) -> ExtractedInvoice:
    fields = (
        db.query(ExtractedFieldModel)
        .filter(ExtractedFieldModel.document_id == doc_id)
        .all()
    )
    field_map = {f.field_name: f.field_value for f in fields}
    line_rows = (
        db.query(LineItemModel)
        .filter(LineItemModel.document_id == doc_id)
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
    return ExtractedInvoice(
        invoice_number=field_map.get("invoice_number"),
        date=field_map.get("date"),
        vendor_name=field_map.get("vendor_name"),
        subtotal=field_map.get("subtotal"),
        tax=field_map.get("tax"),
        total_amount=field_map.get("total_amount"),
        line_items=line_items,
    )


def _reliability_diagram(
    probs: list[float], labels: list[int], n_bins: int = 10
) -> None:
    bin_width = 1.0 / n_bins
    print("\nReliability Diagram (calibrated probs):")
    print("  bin            | n     | mean_pred | mean_actual | gap")
    print("  --------------------------------------------------------")
    for i in range(n_bins):
        lo = i * bin_width
        hi = (i + 1) * bin_width
        in_bin = [
            (p, l) for p, l in zip(probs, labels)
            if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)
        ]
        if not in_bin:
            continue
        avg_p = sum(p for p, _ in in_bin) / len(in_bin)
        avg_l = sum(l for _, l in in_bin) / len(in_bin)
        gap = avg_p - avg_l
        print(
            f"  [{lo:.1f}, {hi:.1f}]    | "
            f"{len(in_bin):5d} | {avg_p:9.4f} | {avg_l:11.4f} | {gap:+.4f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate plausibility verifier")
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to verifier_v{N}.pkl (default: latest in ./models/)",
    )
    parser.add_argument(
        "--n-corrupt", type=int, default=5,
        help="Synthetic negatives per real document for held-out test",
    )
    parser.add_argument(
        "--corrections-holdout", type=int, default=50,
        help="Most-recent corrected documents to use as the real-world test set",
    )
    parser.add_argument("--seed", type=int, default=99)
    args = parser.parse_args(argv)

    if args.model is not None:
        verifier_dir = args.model.parent
    else:
        verifier_dir = _REPO_ROOT / "models"
    verifier = PlausibilityVerifier.from_latest(verifier_dir)
    if verifier is None:
        logger.error(
            "no verifier model found at %s; train one with "
            "`python scripts/train_verifier.py` first",
            verifier_dir,
        )
        return 1

    rng = random.Random(args.seed)
    db = SessionLocal()
    try:
        # Synthetic test: pull recent verified docs (different slice from training)
        from src.backend.db.crud import get_verified_extractions_for_training
        verified_docs = get_verified_extractions_for_training(db, limit=200)
        if not verified_docs:
            logger.warning("no verified docs; skipping synthetic test")
            synthetic_metrics = None
        else:
            synthetic_metrics = _synthetic_eval(
                db, verified_docs, verifier, rng, args.n_corrupt
            )

        # Real-world test: most recent documents that had at least one correction
        corrected_docs = (
            db.query(DocumentModel)
            .join(CorrectionModel, CorrectionModel.document_id == DocumentModel.id)
            .distinct()
            .order_by(DocumentModel.processed_at.desc().nullslast())
            .limit(args.corrections_holdout)
            .all()
        )
        clean_holdout = (
            db.query(DocumentModel)
            .filter(DocumentModel.status == "verified")
            .filter(
                ~DocumentModel.id.in_(
                    db.query(CorrectionModel.document_id).distinct()
                )
            )
            .order_by(DocumentModel.processed_at.desc().nullslast())
            .limit(args.corrections_holdout)
            .all()
        )
        if corrected_docs and clean_holdout:
            real_metrics = _real_eval(db, corrected_docs, clean_holdout, verifier)
        else:
            logger.warning(
                "insufficient corrections data for real-world eval "
                "(corrected=%d, clean=%d)",
                len(corrected_docs),
                len(clean_holdout),
            )
            real_metrics = None
    finally:
        db.close()

    if synthetic_metrics:
        print("\n=== Synthetic Held-Out Test ===")
        print(f"  AUROC : {synthetic_metrics['auroc']:.4f}")
        print(f"  AUPRC : {synthetic_metrics['auprc']:.4f}")
        print(f"  F1    : {synthetic_metrics['f1']:.4f}")
        print(f"  ECE   : {synthetic_metrics['ece']:.4f}")
        _reliability_diagram(synthetic_metrics["probs"], synthetic_metrics["labels"])

    if real_metrics:
        print("\n=== Real-World (Corrections-Based) ===")
        print(f"  Precision (verifier-flagged → was-corrected): {real_metrics['precision']:.4f}")
        print(f"  Recall    (was-corrected → verifier-flagged): {real_metrics['recall']:.4f}")
        print(f"  F1                                          : {real_metrics['f1']:.4f}")

    return 0


def _synthetic_eval(db, docs, verifier, rng, n_corrupt: int) -> dict:
    try:
        import numpy as np
        from sklearn.metrics import average_precision_score, roc_auc_score
    except ImportError as e:
        raise RuntimeError("scikit-learn required for eval") from e

    probs: list[float] = []
    labels: list[int] = []
    for doc in docs:
        inv = _doc_to_invoice(db, doc.id)
        report = verifier.evaluate(inv, doc.confidence_score)
        if report.score is not None:
            probs.append(report.score)
            labels.append(1)
        for _ in range(n_corrupt):
            corrupted = corruption.apply_random(inv, rng)
            if corrupted is None:
                continue
            cr = verifier.evaluate(corrupted.invoice, doc.confidence_score)
            if cr.score is not None:
                probs.append(cr.score)
                labels.append(0)

    if not probs or len(set(labels)) < 2:
        return {"auroc": 0.0, "auprc": 0.0, "f1": 0.0, "ece": 0.0, "probs": probs, "labels": labels}

    auroc = float(roc_auc_score(labels, probs))
    auprc = float(average_precision_score(labels, probs))
    threshold = verifier.threshold
    tp = sum(1 for p, l in zip(probs, labels) if p >= threshold and l == 1)
    fp = sum(1 for p, l in zip(probs, labels) if p >= threshold and l == 0)
    fn = sum(1 for p, l in zip(probs, labels) if p < threshold and l == 1)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    n_bins = 10
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        in_bin = [(p, l) for p, l in zip(probs, labels) if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)]
        if not in_bin:
            continue
        avg_p = sum(p for p, _ in in_bin) / len(in_bin)
        avg_l = sum(l for _, l in in_bin) / len(in_bin)
        ece += (len(in_bin) / n) * abs(avg_p - avg_l)

    return {
        "auroc": auroc, "auprc": auprc, "f1": f1, "ece": ece,
        "probs": probs, "labels": labels,
    }


def _real_eval(db, corrected_docs, clean_docs, verifier) -> dict:
    """Treat 'has at least one correction' as the ground-truth negative label.

    The verifier flags low-plausibility extractions; an extraction needing
    human correction is the closest real-world proxy for an implausible
    automated extraction. Precision = of flagged extractions, what fraction
    were actually corrected. Recall = of corrected extractions, what fraction
    the verifier flagged.
    """
    flagged_corrected = 0
    flagged_clean = 0
    unflagged_corrected = 0
    for doc in corrected_docs:
        inv = _doc_to_invoice(db, doc.id)
        rep = verifier.evaluate(inv, doc.confidence_score)
        if rep.score is None:
            continue
        if not rep.ok:
            flagged_corrected += 1
        else:
            unflagged_corrected += 1
    for doc in clean_docs:
        inv = _doc_to_invoice(db, doc.id)
        rep = verifier.evaluate(inv, doc.confidence_score)
        if rep.score is None:
            continue
        if not rep.ok:
            flagged_clean += 1
    flagged_total = flagged_corrected + flagged_clean
    precision = flagged_corrected / flagged_total if flagged_total else 0.0
    recall = flagged_corrected / max(flagged_corrected + unflagged_corrected, 1)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


if __name__ == "__main__":
    sys.exit(main())
