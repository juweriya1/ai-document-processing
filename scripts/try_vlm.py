"""try_vlm.py — Quick smoke test for VLMExtractor (zero-shot, no training needed).

Loads Qwen2-VL-7B-Instruct in 4-bit and runs extraction on one image.
Use this to verify the model works before kicking off the multi-hour training run.

Usage:
    # Use a CORD test sample (auto-downloaded):
    python scripts/try_vlm.py

    # Use your own image:
    python scripts/try_vlm.py --image path/to/receipt.jpg

    # Use a specific CORD sample index:
    python scripts/try_vlm.py --cord_index 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def load_cord_sample(index: int = 0):
    """Download one CORD v2 test sample and return its PIL image + ground truth."""
    from datasets import load_dataset  # type: ignore[import]
    print(f"Loading CORD v2 test sample #{index} …")
    dataset = load_dataset("naver-clova-ix/cord-v2", split="test")
    row = dataset[index]
    pil_image = row["image"]
    try:
        gt = json.loads(row["ground_truth"])
        gt_parse = gt.get("gt_parse", {})
        ground_truth = {
            "vendor_name": gt_parse.get("store_info", {}).get("store_name"),
            "total_amount": gt_parse.get("total", {}).get("total_price"),
            "subtotal": gt_parse.get("total", {}).get("subtotal_price"),
            "tax": gt_parse.get("total", {}).get("tax_price"),
        }
    except Exception:
        ground_truth = {}
    return pil_image, ground_truth


def load_image_from_path(path: str):
    from PIL import Image  # type: ignore[import]
    print(f"Loading image from {path} …")
    return Image.open(path).convert("RGB"), {}


def run(image_path: str | None, cord_index: int, adapter: str | None) -> None:
    if image_path:
        pil_image, ground_truth = load_image_from_path(image_path)
    else:
        pil_image, ground_truth = load_cord_sample(cord_index)

    print(f"Image size: {pil_image.size}")
    if ground_truth:
        print("\nGround truth:")
        for k, v in ground_truth.items():
            if v:
                print(f"  {k}: {v}")

    print("\nLoading VLMExtractor (this downloads ~15 GB on first run) …")
    t0 = time.time()

    from src.backend.extraction.vlm_extractor import VLMExtractor
    extractor = VLMExtractor(adapter_path=adapter)

    print(f"Model loaded in {time.time() - t0:.1f}s")
    print("\nRunning inference …")
    t1 = time.time()

    fields, line_items = extractor.extract_from_image(pil_image)

    elapsed = time.time() - t1
    print(f"Inference done in {elapsed:.1f}s\n")

    print("=" * 50)
    print("EXTRACTED FIELDS")
    print("=" * 50)
    if fields:
        for f in fields:
            print(f"  {f['field_name']:<20} {f['field_value']:<30}  (conf: {f['confidence']:.2f})")
    else:
        print("  (no fields extracted)")

    if line_items:
        print("\nLINE ITEMS")
        print("=" * 50)
        for item in line_items:
            print(f"  {item.get('description', ''):<30} qty={item.get('quantity', 0)}"
                  f"  unit={item.get('unit_price', 0)}  total={item.get('total', 0)}")

    if ground_truth:
        print("\nCOMPARISON")
        print("=" * 50)
        pred_map = {f["field_name"]: f["field_value"] for f in fields}
        for field, gold in ground_truth.items():
            if not gold:
                continue
            pred = pred_map.get(field, "(missing)")
            match = "✓" if str(gold).strip() == str(pred).strip() else "✗"
            print(f"  {match} {field:<20} gold={gold}  pred={pred}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick VLMExtractor smoke test.")
    parser.add_argument("--image", default=None,
                        help="Path to a receipt/invoice image file.")
    parser.add_argument("--cord_index", type=int, default=0,
                        help="CORD v2 test sample index to use (default: 0).")
    parser.add_argument("--adapter", default=None,
                        help="Path to QLoRA adapter directory (optional).")
    args = parser.parse_args()

    try:
        run(args.image, args.cord_index, args.adapter)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
