"""Evaluate Tier 1 (PaddleOCR + heuristics) and/or Tier 2 (Gemini via BAML)
against the SROIE-v2 dataset using CER / WER.

Why this exists:
- The corrections-table eval (`scripts/eval_ocr_quality.py`) measures only
  fields humans actually edited — selection bias makes the numbers look
  worse than reality.
- SROIE has labeled ground truth for every receipt — no human bottleneck,
  no selection bias, evaluates the model on the WHOLE distribution.
- This is the same dataset used in published papers (ICDAR 2019 SROIE
  challenge), so results here are comparable to the literature.

Usage:
    # Tier 1 only (fast — local OCR, no API cost)
    python scripts/eval_sroie.py --data-dir /path/to/sroie --tier 1

    # Tier 2 only (requires GEMINI_API_KEY; slower; costs money)
    python scripts/eval_sroie.py --data-dir /path/to/sroie --tier 2 --limit 50

    # Both (head-to-head comparison)
    python scripts/eval_sroie.py --data-dir /path/to/sroie --tier both --limit 50

Get the dataset:
    Kaggle: ryanznie/sroie-datasetv2-with-labels
    (or the original ICDAR 2019 SROIE bundle — same loader works on both)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.backend.utils.sroie_loader import (  # noqa: E402
    SroieSample,
    field_coverage,
    iter_samples,
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
logger = logging.getLogger("eval_sroie")


SCALAR_FIELDS = ("invoice_number", "date", "vendor_name",
                 "subtotal", "tax", "total_amount")


# ─────────────────────────────────────────────────────────────────────────
# Tier 1: LocalExtractor (PaddleOCR + heuristics)
# ─────────────────────────────────────────────────────────────────────────

def _build_page_for_image(img_path: Path):
    """Wrap a single SROIE image as a PreprocessedPage so LocalExtractor
    can consume it. Skips the deskew/denoise pipeline — SROIE images are
    already scanned receipts; the page wrapper just provides .original /
    .processed attributes the extractor expects."""
    import cv2  # local import — only needed when --tier 1 runs
    from src.backend.ingestion.preprocessing import PreprocessedPage

    img = cv2.imread(str(img_path))
    if img is None:
        raise RuntimeError(f"could not read image: {img_path}")
    return PreprocessedPage(page_number=0, original=img, processed=img)


async def _run_tier1(samples: list[SroieSample]) -> list[dict]:
    from src.backend.extraction.local_extractor import (
        LocalExtractor, LocalExtractorUnavailable,
    )
    extractor = LocalExtractor()
    out = []
    for i, s in enumerate(samples):
        try:
            page = _build_page_for_image(s.image_path)
            t0 = time.perf_counter()
            result = await extractor.extract([page])
            latency = time.perf_counter() - t0
            out.append({
                "sample": s,
                "tier": "local",
                "fields": result.fields,
                "confidence": result.confidence,
                "latency_s": latency,
                "error": None,
            })
        except LocalExtractorUnavailable as e:
            out.append({"sample": s, "tier": "local", "fields": {},
                        "confidence": 0.0, "latency_s": 0.0,
                        "error": f"unavailable: {e}"})
        except Exception as e:
            logger.exception("tier 1 failed on %s", s.image_path.name)
            out.append({"sample": s, "tier": "local", "fields": {},
                        "confidence": 0.0, "latency_s": 0.0,
                        "error": f"runtime: {e}"})
        if (i + 1) % 5 == 0:
            logger.info("  tier1: %d/%d done", i + 1, len(samples))
    return out


# ─────────────────────────────────────────────────────────────────────────
# Tier 2: NeuralFallback (Gemini via BAML)
# ─────────────────────────────────────────────────────────────────────────

async def _run_tier2(samples: list[SroieSample]) -> list[dict]:
    from src.backend.extraction.neural_fallback import (
        NeuralFallback, NeuralUnavailableError,
    )
    import cv2

    neural = NeuralFallback()
    out = []
    for i, s in enumerate(samples):
        try:
            img = cv2.imread(str(s.image_path))
            if img is None:
                raise RuntimeError(f"could not read image: {s.image_path}")
            t0 = time.perf_counter()
            result = await neural.extract(img)
            latency = time.perf_counter() - t0
            out.append({
                "sample": s,
                "tier": "vlm",
                "fields": result.fields,
                "confidence": result.confidence,
                "latency_s": latency,
                "error": None,
            })
        except NeuralUnavailableError as e:
            out.append({"sample": s, "tier": "vlm", "fields": {},
                        "confidence": 0.0, "latency_s": 0.0,
                        "error": f"unavailable: {e}"})
        except Exception as e:
            logger.exception("tier 2 failed on %s", s.image_path.name)
            out.append({"sample": s, "tier": "vlm", "fields": {},
                        "confidence": 0.0, "latency_s": 0.0,
                        "error": f"runtime: {e}"})
        if (i + 1) % 5 == 0:
            logger.info("  tier2: %d/%d done", i + 1, len(samples))
    return out


# ─────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────

def _per_field_metrics(predictions: list[dict]) -> list[dict]:
    """Per-field CER / WER / normalized-CER aggregated over predictions.

    Skips field-pairs where SROIE has no ground truth (it doesn't carry
    invoice_number, subtotal, or tax) — counting those would penalize
    the model for fields we can't score.
    """
    out = []
    for field in SCALAR_FIELDS:
        pairs = []
        for p in predictions:
            gt = p["sample"].ground_truth.get(field)
            if gt is None:
                continue   # SROIE doesn't supply this field
            hyp = (p["fields"] or {}).get(field)
            pairs.append((gt, hyp))
        if not pairs:
            continue
        c = aggregate_cer(pairs)
        w = aggregate_wer(pairs)
        norm = sum(normalized_cer(r, h) for r, h in pairs) / len(pairs)
        # bucket
        if c < 0.02:   bench = "EXCELLENT"
        elif c < 0.10: bench = "AVERAGE"
        else:          bench = "POOR"
        out.append({
            "field": field, "n": len(pairs),
            "cer": c, "wer": w, "norm_cer": norm, "benchmark": bench,
        })
    return out


def _print_per_field(title: str, rows: list[dict]) -> None:
    if not rows:
        print(f"\n{title}: (no scoreable pairs)")
        return
    print(f"\n{title}")
    print(f"  {'field':<16} {'N':>4} {'CER':>8} {'WER':>8} {'norm_CER':>10}  benchmark")
    print(f"  " + "-" * 60)
    for r in rows:
        print(f"  {r['field']:<16} {r['n']:>4} "
              f"{r['cer'] * 100:>7.2f}% {r['wer'] * 100:>7.2f}% "
              f"{r['norm_cer'] * 100:>9.2f}%  {r['benchmark']}")


def _print_worst_examples(predictions: list[dict], top_n: int = 5) -> None:
    scored = []
    for p in predictions:
        for field in SCALAR_FIELDS:
            gt = p["sample"].ground_truth.get(field)
            if gt is None:
                continue
            hyp = (p["fields"] or {}).get(field)
            c, ops = cer_with_breakdown(gt, hyp)
            scored.append((c, p["tier"], field, p["sample"].image_path.name,
                           gt, hyp, ops))
    if not scored:
        return
    scored.sort(reverse=True)
    print(f"\nTop {top_n} worst predictions (S/D/I tells you the failure mode):")
    for c, tier, field, name, gt, hyp, ops in scored[:top_n]:
        print(f"  CER={c * 100:6.2f}%  tier={tier:6s}  field={field:14s}  "
              f"S={ops.substitutions} D={ops.deletions} I={ops.insertions}  "
              f"img={name}")
        print(f"     gt:    {gt!r}")
        print(f"     model: {hyp!r}")


def _print_latency(predictions: list[dict]) -> None:
    by_tier: dict[str, list[float]] = {}
    for p in predictions:
        if p["latency_s"] > 0:
            by_tier.setdefault(p["tier"], []).append(p["latency_s"])
    for tier, lats in by_tier.items():
        lats.sort()
        def pct(p): return lats[int(round(p * (len(lats) - 1)))]
        print(f"\nLatency  tier={tier}  N={len(lats)}  "
              f"p50={pct(0.5):.2f}s  p95={pct(0.95):.2f}s  max={max(lats):.2f}s")


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

async def _main_async(args) -> int:
    samples = list(iter_samples(Path(args.data_dir)))
    if not samples:
        logger.error("no SROIE samples found at %s", args.data_dir)
        return 1
    if args.limit:
        samples = samples[: args.limit]
    print(f"Loaded {len(samples)} SROIE samples from {args.data_dir}")
    print(f"Field coverage in ground truth (only these can be scored):")
    for f, n in sorted(field_coverage(samples).items()):
        print(f"  {f:<16} {n}/{len(samples)}")

    all_preds = []
    if args.tier in ("1", "both"):
        print("\nRunning Tier 1 (PaddleOCR + heuristics)...")
        t1 = await _run_tier1(samples)
        all_preds.extend(t1)
        _print_per_field("Tier 1 results", _per_field_metrics(t1))
    if args.tier in ("2", "both"):
        print("\nRunning Tier 2 (Gemini via BAML)...")
        t2 = await _run_tier2(samples)
        all_preds.extend(t2)
        _print_per_field("Tier 2 results", _per_field_metrics(t2))

    _print_latency(all_preds)
    _print_worst_examples(all_preds, top_n=args.worst_n)

    if args.tier == "both":
        # Direct comparison
        t1_metrics = {m["field"]: m for m in _per_field_metrics(
            [p for p in all_preds if p["tier"] == "local"])}
        t2_metrics = {m["field"]: m for m in _per_field_metrics(
            [p for p in all_preds if p["tier"] == "vlm"])}
        print("\n=== Head-to-head: Tier 2 CER advantage (positive = Tier 2 wins) ===")
        for field in SCALAR_FIELDS:
            if field in t1_metrics and field in t2_metrics:
                advantage = (t1_metrics[field]["cer"] - t2_metrics[field]["cer"]) * 100
                print(f"  {field:<16}  T1 CER={t1_metrics[field]['cer'] * 100:6.2f}%  "
                      f"T2 CER={t2_metrics[field]['cer'] * 100:6.2f}%  "
                      f"Δ={advantage:+6.2f}pp")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate Tier 1 / Tier 2 extraction against SROIE-v2",
    )
    parser.add_argument(
        "--data-dir", required=True,
        help="Path to the unzipped SROIE dataset (root containing img/ and "
             "key/ or labels/ folders)",
    )
    parser.add_argument(
        "--tier", choices=("1", "2", "both"), default="1",
        help="Which extractor(s) to run (default: 1; 2 needs GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Cap samples (default 50; SROIE has ~600 in full)",
    )
    parser.add_argument(
        "--worst-n", type=int, default=5,
        help="How many worst-CER examples to print (default 5)",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
