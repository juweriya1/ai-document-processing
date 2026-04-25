"""Evaluate Tier 1 vs Tier 2 OCR/extraction quality using CER and WER.

Ground-truth source: the `corrections` table. Every human edit gives us
a `(model_output, human_corrected_value)` pair. By joining against
`documents.fallback_tier`, we can answer:

    "When Tier 1 finalized the extraction, what was the average
     character error rate on the fields humans had to fix?"
    "Same question for Tier 2 — does it earn its API cost?"

Usage:
    python scripts/eval_ocr_quality.py [--limit 1000]

Caveats (be honest about what this measures):
- Only fields a human EDITED appear here. Fields the model got right are
  invisible — this is an upper bound on per-field error among "fields
  humans cared enough to look at." Pair with the verifier eval for the
  whole-pipeline picture.
- A single field can be edited multiple times. We use the EARLIEST
  correction's `original_value` (what the model produced before any
  human touched it).
- Per-field WER on amount fields is essentially "0 if value matches
  exactly, 1 otherwise" since amounts are usually one token. WER is
  reported anyway because it's standard in the OCR literature.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import asc  # noqa: E402

from src.backend.db.database import SessionLocal  # noqa: E402
from src.backend.db.models import (  # noqa: E402
    Correction as CorrectionModel,
    Document as DocumentModel,
    ExtractedField as ExtractedFieldModel,
)
from src.backend.utils.text_metrics import (  # noqa: E402
    aggregate_cer,
    aggregate_wer,
    cer_with_breakdown,
    normalized_cer,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("eval_ocr_quality")


def _load_pairs(db, limit: int):
    """Yield (tier, field_name, model_value, corrected_value) tuples.

    Joins corrections → extracted_fields → documents to bring tier into
    scope. Earliest correction per field wins (that's the model's actual
    output, not a human's intermediate edit).
    """
    earliest_per_field: dict[str, CorrectionModel] = {}
    rows = (
        db.query(CorrectionModel)
        .order_by(asc(CorrectionModel.created_at))
        .limit(limit * 5)  # over-fetch to dedupe by field_id
        .all()
    )
    for row in rows:
        if row.field_id not in earliest_per_field:
            earliest_per_field[row.field_id] = row
    field_to_correction = list(earliest_per_field.values())[:limit]

    for corr in field_to_correction:
        field = (
            db.query(ExtractedFieldModel)
            .filter(ExtractedFieldModel.id == corr.field_id)
            .first()
        )
        if field is None:
            continue
        doc = (
            db.query(DocumentModel)
            .filter(DocumentModel.id == corr.document_id)
            .first()
        )
        if doc is None:
            continue
        tier = doc.fallback_tier or "unknown"
        yield (tier, field.field_name, corr.original_value, corr.corrected_value)


def _print_table(title: str, header: tuple[str, ...], rows: list[tuple]) -> None:
    if not rows:
        print(f"\n{title}: (no data)")
        return
    widths = [
        max(len(str(h)), max((len(str(r[i])) for r in rows), default=0)) + 2
        for i, h in enumerate(header)
    ]
    print(f"\n{title}")
    print("".join(h.ljust(w) for h, w in zip(header, widths)))
    print("".join("-" * w for w in widths))
    for r in rows:
        print("".join(str(c).ljust(w) for c, w in zip(r, widths)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="OCR / extraction quality eval")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        pairs = list(_load_pairs(db, args.limit))
    finally:
        db.close()

    if not pairs:
        print("No corrections in the database — process documents and have a "
              "human submit at least one correction before running this eval.")
        return 0

    print(f"loaded {len(pairs)} corrected (model_output, ground_truth) pairs")
    print(f"  (these are upper-bounded — fields humans never touched are invisible here)")

    # ── Per-field per-tier breakdown ───────────────────────────────────────
    by_tier_field: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for tier, field_name, model_val, gt_val in pairs:
        by_tier_field[(tier, field_name)].append((gt_val, model_val))

    rows = []
    for (tier, field_name), pair_list in sorted(by_tier_field.items()):
        n = len(pair_list)
        c = aggregate_cer(pair_list)
        w = aggregate_wer(pair_list)
        # Mean per-pair normalized CER — bounded so a single huge insertion
        # doesn't blow out the average.
        norms = [normalized_cer(ref, hyp) for ref, hyp in pair_list]
        mean_norm = sum(norms) / len(norms) if norms else 0.0
        rows.append((
            tier, field_name, n,
            f"{c * 100:.2f}%",
            f"{w * 100:.2f}%",
            f"{mean_norm * 100:.2f}%",
        ))
    _print_table(
        "Per-tier × per-field error rates (lower is better; <2% is excellent, >10% is poor)",
        ("tier", "field", "N", "CER", "WER", "norm_CER"),
        rows,
    )

    # ── Tier-level aggregate ──────────────────────────────────────────────
    by_tier: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for tier, _field_name, model_val, gt_val in pairs:
        by_tier[tier].append((gt_val, model_val))
    tier_rows = []
    for tier, pair_list in sorted(by_tier.items()):
        c = aggregate_cer(pair_list)
        w = aggregate_wer(pair_list)
        tier_rows.append((tier, len(pair_list), f"{c * 100:.2f}%", f"{w * 100:.2f}%"))
    _print_table(
        "Tier-level aggregate (all fields combined; tells you which tier "
        "produces fewer / shallower errors)",
        ("tier", "N corrections", "CER", "WER"),
        tier_rows,
    )

    # ── Error-mode breakdown for the worst-performing field ───────────────
    print("\nError-mode breakdown (top 5 worst CER pairs across all tiers — "
          "tells you whether OCR is mostly substituting, deleting, or hallucinating):")
    scored = []
    for tier, field_name, model_val, gt_val in pairs:
        c, ops = cer_with_breakdown(gt_val, model_val)
        scored.append((c, tier, field_name, model_val, gt_val, ops))
    scored.sort(reverse=True)
    for c, tier, field_name, model_val, gt_val, ops in scored[:5]:
        print(f"  CER={c * 100:6.2f}%  tier={tier:6s}  field={field_name:18s}  "
              f"S={ops.substitutions} D={ops.deletions} I={ops.insertions} C={ops.matches}")
        print(f"     gt:    {gt_val!r}")
        print(f"     model: {model_val!r}")

    # ── Conclusions ──────────────────────────────────────────────────────
    print("\nInterpretation guide (Carrasco-style benchmarks for printed text):")
    print("  CER < 2%   → excellent (98%+ accurate)")
    print("  CER 2-10%  → average")
    print("  CER > 10%  → poor; consider re-tuning extraction or escalating earlier")
    if "local" in by_tier and "vlm" in by_tier:
        local_cer = aggregate_cer(by_tier["local"])
        vlm_cer = aggregate_cer(by_tier["vlm"])
        diff = (local_cer - vlm_cer) * 100
        if diff > 2.0:
            print(f"\n→ Tier 2 (Gemini) is producing meaningfully better extractions: "
                  f"{diff:.1f}-pt CER advantage. The escalation cost is paying off.")
        elif diff < -2.0:
            print(f"\n→ Tier 2 is WORSE than Tier 1 by {-diff:.1f}-pt CER on the docs "
                  f"that escalated. Suspect: prompt regression, or escalation "
                  f"happens on the hardest docs (selection bias).")
        else:
            print(f"\n→ Tier 1 and Tier 2 have roughly similar CER ({local_cer * 100:.2f}% "
                  f"vs {vlm_cer * 100:.2f}%). Either selection bias is masking Tier 2's "
                  f"advantage, or you don't need to escalate as often as you do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
