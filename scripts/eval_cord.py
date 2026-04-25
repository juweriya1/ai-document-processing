"""Evaluate Tier 1 / Tier 2 against the CORD-v2 dataset using CER / WER.

Why CORD in addition to SROIE:
  - CORD's ground truth includes line items, subtotal, tax, AND total —
    so we can score 5 of our 6 fields against it. SROIE only covers 3.
  - It loads from HuggingFace `datasets` (no manual download / Kaggle auth).
  - ~100 receipts in the test split; same dataset Qwen2-VL is evaluated on
    in the notebook, so all numbers are directly comparable.

Usage:
    # Tier 1 only (no API cost)
    python scripts/eval_cord.py --tier 1 --limit 50

    # Tier 2 only (needs GEMINI_API_KEY)
    python scripts/eval_cord.py --tier 2 --limit 50

    # Both — head-to-head
    python scripts/eval_cord.py --tier both --limit 50
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

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
logger = logging.getLogger("eval_cord")


SCALAR_FIELDS = ("invoice_number", "date", "vendor_name",
                 "subtotal", "tax", "total_amount")


# ─────────────────────────────────────────────────────────────────────────
# CORD ground-truth → our schema mapping
# ─────────────────────────────────────────────────────────────────────────

def cord_extract_gt(row) -> dict:
    """CORD's gt_parse structure:
        { 'menu': [...], 'sub_total': {'subtotal_price': ...},
          'total': {'total_price': ..., 'tax_price': ...},
          'store_info': {'store_name': ...} }

    `invoice_number` and `date` are usually absent on CORD receipts —
    we report None rather than guessing, so the eval skips them as
    unscoreable (the alternative would penalize the model for a field
    we can't actually score against).
    """
    gt = json.loads(row["ground_truth"])["gt_parse"]
    store = gt.get("store_info", {}) or {}
    totals = gt.get("total", {}) or {}
    sub = gt.get("sub_total", {}) or {}
    return {
        "invoice_number": None,
        "date": None,
        "vendor_name": store.get("store_name"),
        "subtotal": sub.get("subtotal_price"),
        "tax": totals.get("tax_price"),
        "total_amount": totals.get("total_price"),
    }


# ─────────────────────────────────────────────────────────────────────────
# Tier 1 / Tier 2 runners (mirror eval_sroie.py)
# ─────────────────────────────────────────────────────────────────────────

def _build_page_for_pil(pil_image):
    import cv2  # noqa: F401
    import numpy as np
    from src.backend.ingestion.preprocessing import PreprocessedPage
    arr = np.array(pil_image.convert("RGB"))
    return PreprocessedPage(page_number=0, original=arr, processed=arr)


async def _run_tier1(samples) -> list[dict]:
    from src.backend.extraction.local_extractor import (
        LocalExtractor, LocalExtractorUnavailable,
    )
    extractor = LocalExtractor()
    out = []
    for i, s in enumerate(samples):
        try:
            page = _build_page_for_pil(s["image"])
            t0 = time.perf_counter()
            result = await extractor.extract([page])
            latency = time.perf_counter() - t0
            out.append({
                "ground_truth": s["gt"], "tier": "local",
                "fields": result.fields, "latency_s": latency, "error": None,
            })
        except LocalExtractorUnavailable as e:
            out.append({"ground_truth": s["gt"], "tier": "local", "fields": {},
                        "latency_s": 0.0, "error": f"unavailable: {e}"})
        except Exception as e:
            logger.exception("tier 1 failed on sample %d", i)
            out.append({"ground_truth": s["gt"], "tier": "local", "fields": {},
                        "latency_s": 0.0, "error": f"runtime: {e}"})
        if (i + 1) % 5 == 0:
            logger.info("  tier1: %d/%d done", i + 1, len(samples))
    return out


async def _run_tier2(samples) -> list[dict]:
    from src.backend.extraction.neural_fallback import (
        NeuralFallback, NeuralUnavailableError,
    )
    import numpy as np

    neural = NeuralFallback()
    out = []
    for i, s in enumerate(samples):
        try:
            arr = np.array(s["image"].convert("RGB"))
            t0 = time.perf_counter()
            result = await neural.extract(arr)
            latency = time.perf_counter() - t0
            out.append({
                "ground_truth": s["gt"], "tier": "vlm",
                "fields": result.fields, "latency_s": latency, "error": None,
            })
        except NeuralUnavailableError as e:
            out.append({"ground_truth": s["gt"], "tier": "vlm", "fields": {},
                        "latency_s": 0.0, "error": f"unavailable: {e}"})
        except Exception as e:
            logger.exception("tier 2 failed on sample %d", i)
            out.append({"ground_truth": s["gt"], "tier": "vlm", "fields": {},
                        "latency_s": 0.0, "error": f"runtime: {e}"})
        if (i + 1) % 5 == 0:
            logger.info("  tier2: %d/%d done", i + 1, len(samples))
    return out


# ─────────────────────────────────────────────────────────────────────────
# Metrics (same shape as eval_sroie.py for apples-to-apples comparison)
# ─────────────────────────────────────────────────────────────────────────

def _per_field_metrics(predictions: list[dict]) -> list[dict]:
    out = []
    for field in SCALAR_FIELDS:
        pairs = []
        for p in predictions:
            gt = p["ground_truth"].get(field)
            if gt is None:
                continue
            hyp = (p["fields"] or {}).get(field)
            pairs.append((gt, hyp))
        if not pairs:
            continue
        c = aggregate_cer(pairs)
        w = aggregate_wer(pairs)
        norm = sum(normalized_cer(r, h) for r, h in pairs) / len(pairs)
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


def _print_worst(predictions: list[dict], top_n: int = 5) -> None:
    scored = []
    for p in predictions:
        for field in SCALAR_FIELDS:
            gt = p["ground_truth"].get(field)
            if gt is None:
                continue
            hyp = (p["fields"] or {}).get(field)
            c, ops = cer_with_breakdown(gt, hyp)
            scored.append((c, p["tier"], field, gt, hyp, ops))
    scored.sort(reverse=True)
    print(f"\nTop {top_n} worst predictions (S/D/I = substitutions/deletions/insertions):")
    for c, tier, field, gt, hyp, ops in scored[:top_n]:
        print(f"  CER={c * 100:6.2f}%  tier={tier:6s}  field={field:14s}  "
              f"S={ops.substitutions} D={ops.deletions} I={ops.insertions}")
        print(f"     gt:    {gt!r}")
        print(f"     model: {hyp!r}")


def _print_latency(predictions: list[dict]) -> None:
    by_tier = {}
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
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("`datasets` package not installed. "
                     "pip install datasets")
        return 1

    logger.info("loading CORD-v2 from HuggingFace (cached after first run)...")
    dataset = load_dataset("naver-clova-ix/cord-v2", split=args.split)
    logger.info("CORD %s split: %d samples", args.split, len(dataset))

    samples = []
    for i in range(min(args.limit, len(dataset))):
        row = dataset[i]
        samples.append({"image": row["image"], "gt": cord_extract_gt(row)})

    coverage = {f: sum(1 for s in samples if s["gt"].get(f)) for f in SCALAR_FIELDS}
    print(f"Field coverage in CORD ground truth (only these are scoreable):")
    for f, n in coverage.items():
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
    _print_worst(all_preds, top_n=args.worst_n)

    if args.tier == "both":
        t1m = {m["field"]: m for m in _per_field_metrics(
            [p for p in all_preds if p["tier"] == "local"])}
        t2m = {m["field"]: m for m in _per_field_metrics(
            [p for p in all_preds if p["tier"] == "vlm"])}
        print("\n=== Head-to-head: Tier 2 CER advantage (positive = Tier 2 wins) ===")
        for field in SCALAR_FIELDS:
            if field in t1m and field in t2m:
                advantage = (t1m[field]["cer"] - t2m[field]["cer"]) * 100
                print(f"  {field:<16}  T1 CER={t1m[field]['cer'] * 100:6.2f}%  "
                      f"T2 CER={t2m[field]['cer'] * 100:6.2f}%  Δ={advantage:+6.2f}pp")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate Tier 1 / Tier 2 extraction against CORD-v2",
    )
    parser.add_argument("--tier", choices=("1", "2", "both"), default="1")
    parser.add_argument("--limit", type=int, default=50,
                        help="Cap samples (default 50; CORD test has ~100)")
    parser.add_argument("--split", default="test",
                        choices=("train", "validation", "test"),
                        help="CORD split (default: test)")
    parser.add_argument("--worst-n", type=int, default=5)
    args = parser.parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
