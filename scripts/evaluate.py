"""evaluate.py — FADE field-extraction benchmarking script.

Evaluates EntityExtractor (baseline) or VLMExtractor against CORD or SROIE test sets.
Reports per-field exact match and token-level F1, saves a CSV results table.

Usage examples:
  python scripts/evaluate.py --dataset cord --extractor baseline
  python scripts/evaluate.py --dataset cord --extractor vlm
  python scripts/evaluate.py --dataset sroie --extractor vlm --adapter /path/to/adapter
  python scripts/evaluate.py --dataset cord --extractor vlm --output results/cord_vlm.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataset field mapping
# ---------------------------------------------------------------------------

# CORD v2 → canonical field names used in this project
CORD_FIELD_MAP = {
    "menu.nm": "vendor_name",      # store name lives in the first menu block; handled separately
    "total.total_price": "total_amount",
    "total.subtotal_price": "subtotal",
    "total.tax_price": "tax",
}

# SROIE → canonical field names
SROIE_FIELD_MAP = {
    "company": "vendor_name",
    "date": "date",
    "address": "vendor_name",   # address used as secondary vendor signal
    "total": "total_amount",
}


# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------

def load_cord_test_set() -> list[dict[str, Any]]:
    """Load CORD v2 test split from HuggingFace datasets.

    Returns:
        List of dicts with keys: "image" (PIL.Image) and "ground_truth" (dict of field→value).
    """
    from datasets import load_dataset  # type: ignore[import]

    logger.info("Loading CORD v2 test split …")
    dataset = load_dataset("naver-clova-ix/cord-v2", split="test")
    samples = []

    for row in dataset:
        pil_image = row["image"]
        try:
            gt_raw = json.loads(row["ground_truth"])
        except (json.JSONDecodeError, KeyError):
            continue

        gt: dict[str, str] = {}

        # Extract company/store name from the top of the receipt
        store_nm = gt_raw.get("gt_parse", {}).get("store_info", {}).get("store_name", "")
        if store_nm:
            gt["vendor_name"] = str(store_nm).strip()

        # Extract total, subtotal, tax
        total_info = gt_raw.get("gt_parse", {}).get("total", {})
        if total_info.get("total_price"):
            gt["total_amount"] = _normalise_amount(str(total_info["total_price"]))
        if total_info.get("subtotal_price"):
            gt["subtotal"] = _normalise_amount(str(total_info["subtotal_price"]))
        if total_info.get("tax_price"):
            gt["tax"] = _normalise_amount(str(total_info["tax_price"]))

        samples.append({"image": pil_image, "ground_truth": gt})

    logger.info("Loaded %d CORD test samples", len(samples))
    return samples


def load_sroie_test_set() -> list[dict[str, Any]]:
    """Load SROIE test split from HuggingFace datasets.

    Returns:
        List of dicts with keys: "image" (PIL.Image) and "ground_truth" (dict of field→value).
    """
    from datasets import load_dataset  # type: ignore[import]

    logger.info("Loading SROIE test split …")
    # The SROIE dataset on HuggingFace uses the 'darentang/sroie' configuration
    try:
        dataset = load_dataset("darentang/sroie", "original", split="test", trust_remote_code=True)
    except Exception:
        dataset = load_dataset("darentang/sroie", split="test", trust_remote_code=True)

    samples = []
    for row in dataset:
        pil_image = row.get("image") or row.get("img")
        if pil_image is None:
            continue

        gt: dict[str, str] = {}
        for sroie_key, canonical in SROIE_FIELD_MAP.items():
            value = row.get(sroie_key, "")
            if value and str(value).strip():
                # For SROIE 'total' is always the amount
                if canonical == "total_amount":
                    value = _normalise_amount(str(value))
                gt[canonical] = str(value).strip()
            # Prefer 'company' over 'address' for vendor_name
            if sroie_key == "company" and value:
                gt["vendor_name"] = str(value).strip()

        samples.append({"image": pil_image, "ground_truth": gt})

    logger.info("Loaded %d SROIE test samples", len(samples))
    return samples


# ---------------------------------------------------------------------------
# Extraction runner
# ---------------------------------------------------------------------------

def run_extraction_baseline(sample: dict[str, Any]) -> dict[str, str]:
    """Run EntityExtractor (baseline) on a sample image.

    Saves the PIL image to a tmp PDF, runs OCR + EntityExtractor, returns
    predicted fields as {field_name: field_value}.
    """
    from PIL import Image
    from src.backend.ocr.ocr_engine import DocumentOCRResult, OCREngine, OCRResult
    from src.backend.extraction.entity_extractor import EntityExtractor

    pil_image = sample["image"]
    if not isinstance(pil_image, Image.Image):
        return {}

    # Write image to temp PNG, run EasyOCR fallback (no GPU needed for baseline)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pil_image.save(tmp_path)
        import numpy as np
        img_array = np.array(pil_image.convert("L"))
        engine = OCREngine(use_got_ocr=False)
        ocr_result_page = engine.extract_text_from_image(img_array, page_number=1)
        doc_result = DocumentOCRResult(
            pages=[ocr_result_page],
            tables=[],
            full_text=ocr_result_page.text,
        )
        extractor = EntityExtractor()
        extracted = extractor.extract(doc_result)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return {f["field_name"]: f["field_value"] for f in extracted.fields}


def run_extraction_vlm(
    sample: dict[str, Any], adapter_path: str | None = None
) -> dict[str, str]:
    """Run VLMExtractor on a sample image (GPU required).

    Uses extract_from_image() which bypasses PDF preprocessing — suitable
    for dataset evaluation where samples are already PIL images.
    """
    from PIL import Image
    from src.backend.extraction.vlm_extractor import VLMExtractor

    pil_image = sample["image"]
    if not isinstance(pil_image, Image.Image):
        return {}
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    extractor = VLMExtractor(adapter_path=adapter_path)
    fields, _ = extractor.extract_from_image(pil_image)
    return {f["field_name"]: f["field_value"] for f in fields}


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _normalise_amount(value: str) -> str:
    """Strip currency symbols, commas, leading zeros; normalise to 2 dp string."""
    cleaned = re.sub(r"[^\d.]", "", value.strip())
    try:
        return f"{float(cleaned):.2f}"
    except ValueError:
        return cleaned


def _normalise_text(value: str) -> str:
    """Lowercase, collapse whitespace for soft string comparison."""
    return re.sub(r"\s+", " ", value.strip().lower())


def _tokenise(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _token_f1(pred: str, gold: str) -> float:
    """Compute token-level F1 between two strings (standard SQuAD metric)."""
    pred_tokens = _tokenise(pred)
    gold_tokens = _tokenise(gold)
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = set(pred_tokens) & set(gold_tokens)
    n_common = sum(min(pred_tokens.count(t), gold_tokens.count(t)) for t in common)
    if n_common == 0:
        return 0.0
    precision = n_common / len(pred_tokens)
    recall = n_common / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def compute_metrics(
    predictions: list[dict[str, str]],
    ground_truths: list[dict[str, str]],
    fields: list[str],
) -> dict[str, dict[str, float]]:
    """Compute per-field exact match and F1.

    Returns:
        {field_name: {"exact_match": float, "f1": float, "n_samples": int}}
    """
    results: dict[str, dict[str, Any]] = {
        f: {"exact_match_sum": 0, "f1_sum": 0.0, "n": 0} for f in fields
    }

    for pred, gold in zip(predictions, ground_truths):
        for field in fields:
            gold_val = gold.get(field, "")
            if not gold_val:
                continue  # skip samples where gold label is missing

            pred_val = pred.get(field, "")
            results[field]["n"] += 1

            gold_norm = _normalise_text(gold_val)
            pred_norm = _normalise_text(pred_val)

            results[field]["exact_match_sum"] += int(pred_norm == gold_norm)
            results[field]["f1_sum"] += _token_f1(pred_norm, gold_norm)

    out = {}
    for field, data in results.items():
        n = data["n"]
        out[field] = {
            "exact_match": data["exact_match_sum"] / n if n else 0.0,
            "f1": data["f1_sum"] / n if n else 0.0,
            "n_samples": n,
        }

    return out


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def save_results_csv(
    metrics: dict[str, dict[str, float]],
    dataset: str,
    extractor: str,
    output_path: str,
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write_header = not Path(output_path).exists()
    with open(output_path, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["dataset", "extractor", "field", "exact_match", "f1", "n_samples"])
        for field, data in sorted(metrics.items()):
            writer.writerow([
                dataset,
                extractor,
                field,
                f"{data['exact_match']:.4f}",
                f"{data['f1']:.4f}",
                data["n_samples"],
            ])
    logger.info("Results saved to %s", output_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FIELDS_CORD = ["vendor_name", "total_amount", "subtotal", "tax"]
FIELDS_SROIE = ["vendor_name", "date", "total_amount"]
FIELDS_ALL = ["invoice_number", "vendor_name", "date", "total_amount", "subtotal", "tax"]


def _print_table(metrics: dict[str, dict[str, float]], dataset: str, extractor: str) -> None:
    print(f"\n{'='*62}")
    print(f"  Dataset: {dataset}   Extractor: {extractor}")
    print(f"{'='*62}")
    print(f"  {'Field':<20} {'Exact Match':>12} {'F1':>8} {'N':>6}")
    print(f"  {'-'*46}")
    for field, data in sorted(metrics.items()):
        print(
            f"  {field:<20} {data['exact_match']:>12.4f} "
            f"{data['f1']:>8.4f} {data['n_samples']:>6}"
        )
    print(f"{'='*62}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate FADE field extraction against CORD or SROIE test sets."
    )
    parser.add_argument(
        "--dataset", choices=["cord", "sroie"], required=True,
        help="Evaluation dataset."
    )
    parser.add_argument(
        "--extractor", choices=["baseline", "vlm"], required=True,
        help="baseline = EntityExtractor (EasyOCR + spaCy); vlm = VLMExtractor (Qwen2-VL-7B)."
    )
    parser.add_argument(
        "--adapter", default=None,
        help="Path to QLoRA adapter directory (vlm extractor only)."
    )
    parser.add_argument(
        "--output", default="results/eval_results.csv",
        help="Output CSV path (rows are appended if file exists)."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit evaluation to first N samples (useful for quick smoke tests)."
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load samples
    # ------------------------------------------------------------------
    if args.dataset == "cord":
        samples = load_cord_test_set()
        eval_fields = FIELDS_CORD
    else:
        samples = load_sroie_test_set()
        eval_fields = FIELDS_SROIE

    if args.limit:
        samples = samples[: args.limit]
        logger.info("Limiting to %d samples", len(samples))

    # ------------------------------------------------------------------
    # Run extraction
    # ------------------------------------------------------------------
    predictions: list[dict[str, str]] = []
    ground_truths: list[dict[str, str]] = []

    for i, sample in enumerate(samples):
        if i % 10 == 0:
            logger.info("Processing sample %d / %d …", i + 1, len(samples))
        try:
            if args.extractor == "baseline":
                pred = run_extraction_baseline(sample)
            else:
                pred = run_extraction_vlm(sample, adapter_path=args.adapter)
        except Exception as exc:
            logger.warning("Sample %d failed: %s", i, exc)
            pred = {}

        predictions.append(pred)
        ground_truths.append(sample["ground_truth"])

    # ------------------------------------------------------------------
    # Compute + report metrics
    # ------------------------------------------------------------------
    metrics = compute_metrics(predictions, ground_truths, eval_fields)
    _print_table(metrics, args.dataset, args.extractor)
    save_results_csv(metrics, args.dataset, args.extractor, args.output)


if __name__ == "__main__":
    main()
