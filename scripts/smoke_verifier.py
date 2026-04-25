"""End-to-end smoke for the plausibility verifier.

Generates synthetic invoices in memory, trains a verifier artifact, reloads
it through PlausibilityVerifier.from_latest, and scores fresh clean+
corrupted samples. No DB required — useful for smoke-testing on a fresh
checkout before any real documents have been processed.

Run:
    python scripts/smoke_verifier.py [--n-train 80] [--out models/]
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.backend.agents.state import ExtractedInvoice, LineItem  # noqa: E402
from src.backend.verifier import PlausibilityVerifier  # noqa: E402
from src.backend.verifier import corruption  # noqa: E402
from src.backend.verifier.trainer import TrainConfig, train  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("smoke_verifier")


def _fake_invoice(seed: int) -> ExtractedInvoice:
    """Generate a structurally clean synthetic invoice.

    Math always balances (subtotal + tax == total), line-item arithmetic
    holds, dates are recent and well-formed, vendor names are plausible.
    """
    rng = random.Random(seed)
    n_items = rng.randint(2, 5)
    line_items = []
    subtotal = Decimal(0)
    for i in range(n_items):
        qty = Decimal(str(rng.randint(1, 8)))
        unit = Decimal(str(round(rng.uniform(5.0, 250.0), 2)))
        total = qty * unit
        subtotal += total
        line_items.append(
            LineItem(
                description=f"Item {chr(65 + i)}",
                quantity=str(qty),
                unit_price=f"{unit:.2f}",
                total=f"{total:.2f}",
            )
        )
    tax = (subtotal * Decimal("0.15")).quantize(Decimal("0.01"))
    total = subtotal + tax
    vendor = rng.choice([
        "Acme Corp", "Globex Industries", "Initech LLC",
        "Hooli Tech", "Soylent Foods", "Wayne Enterprises",
        "Stark Manufacturing",
    ])
    day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    year = rng.choice([2023, 2024, 2025])
    return ExtractedInvoice(
        invoice_number=f"INV-{year}-{rng.randint(1000, 9999)}",
        date=f"{day:02d}/{month:02d}/{year}",
        vendor_name=vendor,
        subtotal=f"{subtotal:.2f}",
        tax=f"{tax:.2f}",
        total_amount=f"{total:.2f}",
        line_items=line_items,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifier end-to-end smoke")
    parser.add_argument("--n-train", type=int, default=80)
    parser.add_argument("--n-test", type=int, default=20)
    parser.add_argument("--negatives", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output dir (default: a fresh tempdir). Use models/ for the real one.",
    )
    args = parser.parse_args(argv)

    out_dir = args.out or Path(tempfile.mkdtemp(prefix="verifier_smoke_"))
    logger.info("output dir: %s", out_dir)

    # 1. Generate synthetic clean training set.
    train_invoices = [_fake_invoice(seed=args.seed + i) for i in range(args.n_train)]
    logger.info("generated %d synthetic clean invoices", len(train_invoices))

    # 2. Train.
    cfg = TrainConfig(negatives_per_positive=args.negatives, seed=args.seed)
    report = train(train_invoices, cfg=cfg, output_dir=out_dir)
    logger.info("training complete:")
    logger.info("  positives          : %d", report.n_positives)
    logger.info("  negatives          : %d", report.n_negatives)
    logger.info("  features           : %d", report.n_features)
    logger.info("  val AUROC          : %.4f", report.val_auroc)
    logger.info("  val AUPRC          : %.4f", report.val_auprc)
    logger.info("  val F1             : %.4f", report.val_f1)
    logger.info("  threshold (F1-opt) : %.4f", report.threshold)
    logger.info("  ECE pre-cal        : %.4f", report.pre_calibration_ece)
    logger.info("  ECE post-cal       : %.4f", report.post_calibration_ece)
    logger.info("  artifact           : %s", report.artifact_path)
    if report.per_operator_recall:
        logger.info("  per-operator recall (corruption type → caught fraction):")
        for op, recall in sorted(
            report.per_operator_recall.items(), key=lambda kv: kv[1], reverse=True
        ):
            logger.info("    %-22s %.3f", op, recall)

    # 3. Reload through the production loader path (proves cold-start →
    #    has-model transition works end-to-end).
    verifier = PlausibilityVerifier.from_latest(out_dir)
    if verifier is None:
        logger.error("failed to load trained artifact — predictor returned None")
        return 1
    logger.info("reloaded artifact: threshold=%.4f", verifier.threshold)

    # 4. Score held-out clean + corrupted samples.
    rng = random.Random(args.seed + 9999)
    test_invoices = [
        _fake_invoice(seed=args.seed + 1_000 + i) for i in range(args.n_test)
    ]
    n_clean_correct = 0
    n_corrupted_correct = 0
    n_corrupted_seen = 0
    print("\n--- Held-out test scoring ---")
    print(f"{'kind':22s} {'op':22s} {'score':>7s} {'verdict':>8s}")
    for inv in test_invoices:
        rep = verifier.evaluate(inv, ocr_confidence=0.93)
        if rep.ok:
            n_clean_correct += 1
        print(f"{'clean':22s} {'-':22s} {rep.score:7.4f} {('OK' if rep.ok else 'FLAG'):>8s}")
        for _ in range(args.negatives):
            cr = corruption.apply_random(inv, rng)
            if cr is None:
                continue
            n_corrupted_seen += 1
            crep = verifier.evaluate(cr.invoice, ocr_confidence=0.93)
            if not crep.ok:
                n_corrupted_correct += 1
            print(
                f"{'corrupted':22s} {cr.operator:22s} "
                f"{crep.score:7.4f} {('OK' if crep.ok else 'FLAG'):>8s}"
            )

    print("\n--- Held-out summary ---")
    print(f"  clean recognized as plausible : {n_clean_correct}/{len(test_invoices)} "
          f"= {n_clean_correct / max(len(test_invoices), 1):.2%}")
    print(f"  corrupted caught              : {n_corrupted_correct}/{n_corrupted_seen} "
          f"= {n_corrupted_correct / max(n_corrupted_seen, 1):.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
