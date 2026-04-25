"""Construct the Qwen2-VL evaluation notebook.

Run with:
    python notebooks/_build_qwen_notebook.py

Outputs notebooks/qwen.ipynb. The source of each cell lives in this
script so multi-line Python can be written plainly without wrestling
with JSON escapes.
"""

from __future__ import annotations

import json
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parent / "qwen.ipynb"


def md(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": _split(source),
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _split(source),
    }


def _split(source: str) -> list[str]:
    lines = source.lstrip("\n").splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    # Jupyter stores source as a list of strings where each item ends in \n
    # except optionally the last. We always terminate so git diffs stay stable.
    return lines


CELLS: list[dict] = []


# ─────────────────────────────────────────────────────────────────────────────
# 1. Title & objectives
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
# Qwen2-VL-7B Evaluation for Invoice Extraction

**Goal:** figure out exactly where Qwen2-VL-7B (4-bit quantized, zero-shot)
succeeds and fails on CORD-v2 receipts so the QLoRA fine-tuning plan can
target the weaknesses instead of burning compute on fields the model
already nails.

This notebook is deliberately structured so every answer is backed by
measurements, not vibes:

1. Load the 4-bit quantized model
2. Sanity check on one sample
3. Run a held-out evaluation on N documents
4. Per-field precision / recall / F1 with exact + fuzzy + numeric matching
5. JSON parse robustness (a common VLM failure mode)
6. Line-item count accuracy
7. Latency distribution (p50 / p95)
8. Error taxonomy with concrete examples for each weak field
9. Conclusions + QLoRA fine-tuning recipe

Run the cells top-to-bottom. Adjust `N_SAMPLES` in the evaluation cell
if you want a faster / bigger run.
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Imports & environment
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(code("""
import os
import re
import json
import time
import math
from collections import defaultdict, Counter
from statistics import median

import torch
from datasets import load_dataset
from transformers import (
    Qwen2VLForConditionalGeneration,
    AutoProcessor,
    BitsAndBytesConfig,
)
from qwen_vl_utils import process_vision_info

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"
print("torch:", torch.__version__, "cuda:", torch.cuda.is_available())
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Load dataset (small split)
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(code("""
# CORD-v2 test split has ~100 receipts. We'll evaluate on a subset and
# keep the rest for the QLoRA train/val partition later.
dataset = load_dataset("naver-clova-ix/cord-v2", split="test")
print(f"CORD test size: {len(dataset)}")

# Peek at one ground-truth to remind ourselves of the schema
example_gt = json.loads(dataset[0]["ground_truth"])["gt_parse"]
print("CORD gt_parse keys (sample):", list(example_gt.keys()))
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Load model
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(code("""
print("Loading Qwen2-VL-7B (4-bit NF4)...")
bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
)

model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2-VL-7B-Instruct",
    quantization_config=bnb,
    device_map="auto",
    low_cpu_mem_usage=True,
    torch_dtype=torch.float16,
)
processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")
print(f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Prompt + single-sample sanity check
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Sanity check

Before we evaluate on many samples, confirm the model is actually producing
extractions on the first CORD receipt. If this cell prints JSON with at
least `vendor_name` and `total_amount` populated, we're good to proceed.
If it prints garbage, stop and fix the prompt before evaluating 50 samples.
"""))


CELLS.append(code("""
PROMPT = (
    "Return ONLY valid JSON. No explanation. No text outside JSON.\\n"
    "If a field is not visible, write null. Do not guess.\\n\\n"
    "Fields:\\n"
    "- invoice_number (string or null)\\n"
    "- date (string or null, preserve the format on the receipt)\\n"
    "- vendor_name (string or null)\\n"
    "- subtotal (string or null, include currency marker if present)\\n"
    "- tax (string or null, include currency marker if present)\\n"
    "- total_amount (string or null, include currency marker if present)\\n"
    "- line_items (list of objects with description, quantity, unit_price, total)\\n"
)


def generate_extraction(image, max_new_tokens=512):
    \"\"\"Run the model once; return (raw_text, latency_seconds).\"\"\"
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": PROMPT},
        ],
    }]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text], images=image_inputs, videos=video_inputs,
        padding=True, return_tensors="pt",
    ).to(model.device)

    start = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens)
    latency = time.perf_counter() - start

    raw = processor.batch_decode(
        out[:, inputs.input_ids.shape[1]:],
        skip_special_tokens=True,
    )[0]
    return raw, latency


# Sanity check
sample_img = dataset[0]["image"].convert("RGB")
raw, lat = generate_extraction(sample_img)
print(f"Latency: {lat:.2f}s")
print("--- RAW OUTPUT ---")
print(raw)
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Matching & normalization
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Matching functions

Exact string comparison is too strict for a VLM on receipt data. We classify
every field prediction into one of these buckets:

- **exact**: normalized strings identical (lowercased, stripped, no currency markers)
- **numeric_ok**: for amount fields, parsed Decimals within ±$0.02
- **fuzzy**: Levenshtein distance ≤ 2 after normalization (captures OCR-style misreads)
- **wrong**: prediction is non-null but doesn't match the ground truth
- **miss**: ground truth has a value, model returned null / missing
- **hallucination**: model returned a value but ground truth has none

From these buckets we compute the real metrics: precision, recall, F1.
"""))


CELLS.append(code("""
from decimal import Decimal, InvalidOperation

_CURRENCY_RE = re.compile(r"(rs\\.?|pkr|inr|usd|\\$|€|£|/-)", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\\s+")


def normalize_text(x):
    if x is None:
        return None
    s = str(x).strip().lower()
    s = _CURRENCY_RE.sub("", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    s = s.replace(",", "")
    return s if s else None


def parse_amount(x):
    if x is None:
        return None
    s = normalize_text(x)
    if s is None:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j-1] + 1, prev[j] + 1, prev[j-1] + cost)
        prev = curr
    return prev[-1]


AMOUNT_FIELDS = {"subtotal", "tax", "total_amount"}
NUMERIC_TOLERANCE = Decimal("0.02")


def classify(pred, gt, field: str) -> str:
    \"\"\"Return one of: exact | numeric_ok | fuzzy | wrong | miss | hallucination | both_null.\"\"\"
    if gt is None and pred is None:
        return "both_null"
    if gt is None and pred is not None:
        return "hallucination"
    if gt is not None and pred is None:
        return "miss"

    np_pred = normalize_text(pred)
    np_gt = normalize_text(gt)
    if np_pred == np_gt:
        return "exact"

    if field in AMOUNT_FIELDS:
        p_dec = parse_amount(pred)
        g_dec = parse_amount(gt)
        if p_dec is not None and g_dec is not None and abs(p_dec - g_dec) <= NUMERIC_TOLERANCE:
            return "numeric_ok"

    if np_pred and np_gt and levenshtein(np_pred, np_gt) <= 2:
        return "fuzzy"

    return "wrong"


# Quick sanity
assert classify("ACME Corp", "acme corp", "vendor_name") == "exact"
assert classify("$100.00", "100", "total_amount") == "numeric_ok"
assert classify("Acmme Corp", "Acme Corp", "vendor_name") == "fuzzy"
assert classify(None, "x", "vendor_name") == "miss"
assert classify("x", None, "vendor_name") == "hallucination"
print("classify() sanity checks pass")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 7. CORD ground truth extractor
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(code("""
def extract_gt(row) -> dict:
    \"\"\"Map CORD-v2 gt_parse into our 7-field schema.

    CORD's structure:
      { \"menu\": [...], \"sub_total\": {\"subtotal_price\": ...},
        \"total\": {\"total_price\": ..., \"tax_price\": ...},
        \"store_info\": {\"store_name\": ...} }

    invoice_number is frequently absent in CORD (they're receipts, not
    formal invoices) — we represent that as None so 'miss' is counted
    fairly.
    \"\"\"
    gt = json.loads(row["ground_truth"])["gt_parse"]
    store = gt.get("store_info", {}) or {}
    totals = gt.get("total", {}) or {}
    sub = gt.get("sub_total", {}) or {}
    menu = gt.get("menu", []) or []
    if isinstance(menu, dict):
        menu = [menu]

    line_items = []
    for item in menu:
        if not isinstance(item, dict):
            continue
        line_items.append({
            "description": item.get("nm"),
            "quantity": item.get("cnt"),
            "unit_price": item.get("price"),
            "total": item.get("price"),  # CORD doesn't separate unit_price from total for most entries
        })

    return {
        "invoice_number": None,   # CORD receipts rarely carry explicit invoice numbers
        "date": None,             # Likewise — date often absent from CORD
        "vendor_name": store.get("store_name"),
        "subtotal": sub.get("subtotal_price"),
        "tax": totals.get("tax_price"),
        "total_amount": totals.get("total_price"),
        "line_items": line_items,
    }


print("GT for sample 0:", extract_gt(dataset[0]))
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 8. Run-one wrapper
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(code("""
def parse_json_output(raw: str):
    \"\"\"Best-effort JSON extraction from a VLM reply.

    Returns (parsed_dict_or_None, parse_failure_reason_or_None).
    \"\"\"
    if not raw:
        return None, "empty_output"
    # Strip code fences if the model decided to wrap the JSON
    cleaned = re.sub(r"^```(?:json)?\\s*|\\s*```$", "", raw.strip(), flags=re.MULTILINE)
    match = re.search(r"\\{.*\\}", cleaned, re.DOTALL)
    if not match:
        return None, "no_json_found"
    try:
        return json.loads(match.group()), None
    except json.JSONDecodeError as e:
        return None, f"json_decode_error: {e.msg}"


def run_one(row) -> dict:
    img = row["image"].convert("RGB")
    raw, latency = generate_extraction(img)
    parsed, parse_err = parse_json_output(raw)
    return {
        "image_size": img.size,
        "raw_output": raw,
        "parsed": parsed,
        "parse_error": parse_err,
        "latency_s": latency,
        "gt": extract_gt(row),
    }
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 9. Evaluation loop
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Evaluation run

`N_SAMPLES` controls the trade-off between statistical strength and
runtime. On a single A100 MIG 20GB at 4-bit, each sample takes ~3–8
seconds depending on image size and output length. 50 samples ≈ 4–7
minutes; 100 ≈ 8–15. Set lower for a smoke test.
"""))


CELLS.append(code("""
N_SAMPLES = 50
results = []
start_eval = time.time()
for i in range(min(N_SAMPLES, len(dataset))):
    row = dataset[i]
    try:
        results.append(run_one(row))
    except Exception as e:
        results.append({
            "raw_output": None,
            "parsed": None,
            "parse_error": f"generation_exception: {e}",
            "latency_s": 0.0,
            "gt": extract_gt(row),
        })
    if (i + 1) % 5 == 0:
        elapsed = time.time() - start_eval
        eta = elapsed / (i + 1) * (N_SAMPLES - (i + 1))
        print(f"  {i + 1}/{N_SAMPLES} done  ·  ETA ~{eta:.0f}s")
print(f"evaluated {len(results)} samples in {time.time() - start_eval:.1f}s")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Per-field metrics
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Per-field metrics

Precision = TP / (TP + FP + hallucinations). Recall = TP / (TP + FN + misses).
F1 = harmonic mean. We count `exact`, `numeric_ok`, and `fuzzy` as true
positives (with decreasing confidence). This is a forgiving but honest read
of correctness.
"""))


CELLS.append(code("""
SCALAR_FIELDS = [
    "invoice_number", "date", "vendor_name",
    "subtotal", "tax", "total_amount",
]
TP_BUCKETS = {"exact", "numeric_ok", "fuzzy"}


def compute_field_metrics(results, field: str) -> dict:
    buckets = Counter()
    for r in results:
        pred_parsed = r.get("parsed") or {}
        pred = pred_parsed.get(field) if isinstance(pred_parsed, dict) else None
        gt = (r.get("gt") or {}).get(field)
        buckets[classify(pred, gt, field)] += 1

    tp = sum(buckets[b] for b in TP_BUCKETS)
    fp = buckets["wrong"] + buckets["hallucination"]
    fn = buckets["miss"] + buckets["wrong"]  # wrong counts as both FP and FN for F1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "field": field,
        "exact": buckets["exact"],
        "numeric_ok": buckets["numeric_ok"],
        "fuzzy": buckets["fuzzy"],
        "wrong": buckets["wrong"],
        "miss": buckets["miss"],
        "hallucination": buckets["hallucination"],
        "both_null": buckets["both_null"],
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


field_metrics = [compute_field_metrics(results, f) for f in SCALAR_FIELDS]

# Pretty print
print(f"{'field':<18} {'P':>6} {'R':>6} {'F1':>6} "
      f"{'exact':>6} {'num':>5} {'fuzzy':>6} {'wrong':>6} "
      f"{'miss':>6} {'halluc':>7} {'both∅':>6}")
print("-" * 98)
for m in sorted(field_metrics, key=lambda x: x["f1"], reverse=True):
    print(f"{m['field']:<18} "
          f"{m['precision']:>6.3f} {m['recall']:>6.3f} {m['f1']:>6.3f} "
          f"{m['exact']:>6} {m['numeric_ok']:>5} {m['fuzzy']:>6} {m['wrong']:>6} "
          f"{m['miss']:>6} {m['hallucination']:>7} {m['both_null']:>6}")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 11. JSON parse robustness
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## JSON parse robustness

How often does the model output parseable JSON? If parse failures are
common (>5%), either the prompt needs tightening or JSON schema-forcing
during generation (grammar-constrained decoding) becomes a required
part of the production recipe.
"""))


CELLS.append(code("""
parse_ok = sum(1 for r in results if r.get("parsed") is not None)
parse_fail = len(results) - parse_ok

failure_reasons = Counter(
    (r.get("parse_error") or "unknown_reason")
    for r in results
    if r.get("parsed") is None
)

print(f"parse success: {parse_ok}/{len(results)} = {parse_ok/max(len(results),1):.1%}")
print(f"parse failures: {parse_fail}")
for reason, n in failure_reasons.most_common():
    print(f"  {reason}: {n}")

if parse_fail:
    print("\\n--- Example failed raw output (first one) ---")
    for r in results:
        if r.get("parsed") is None:
            print(r.get("raw_output") or "(empty)")
            break
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 12. Line items
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Line item extraction

CORD receipts have a variable number of items. Three checks:

1. How often does the model return the correct *count*?
2. How often is the description + price of each line item approximately right?
3. When wrong, does the model over-count (hallucinated items) or under-count (missed items)?
"""))


CELLS.append(code("""
count_match = 0
count_over = 0
count_under = 0
item_desc_matches = 0
item_desc_total = 0

for r in results:
    pred = (r.get("parsed") or {}).get("line_items") if r.get("parsed") else None
    gt_items = r.get("gt", {}).get("line_items") or []
    pred_items = pred if isinstance(pred, list) else []

    if len(pred_items) == len(gt_items):
        count_match += 1
    elif len(pred_items) > len(gt_items):
        count_over += 1
    else:
        count_under += 1

    # Item-level: try to match descriptions in positional order
    for pi, gi in zip(pred_items, gt_items):
        if not isinstance(pi, dict) or not isinstance(gi, dict):
            continue
        item_desc_total += 1
        pd = normalize_text(pi.get("description"))
        gd = normalize_text(gi.get("description"))
        if pd and gd and (pd == gd or levenshtein(pd, gd) <= 3):
            item_desc_matches += 1

print(f"line_item count match: {count_match}/{len(results)} = {count_match/max(len(results),1):.1%}")
print(f"  over-count  : {count_over}")
print(f"  under-count : {count_under}")
if item_desc_total:
    print(f"positional description match (where counts align): "
          f"{item_desc_matches}/{item_desc_total} = "
          f"{item_desc_matches/item_desc_total:.1%}")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 13. Latency
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Latency

Tells us the cost profile for production inference (if we ever self-host)
and for training throughput (one training step ≈ one forward + one
backward, so pure-inference latency is a lower bound on training step
time).
"""))


CELLS.append(code("""
lats = [r.get("latency_s", 0.0) for r in results if r.get("latency_s")]
if lats:
    lats_sorted = sorted(lats)
    def pct(p):
        k = int(round(p * (len(lats_sorted) - 1)))
        return lats_sorted[k]
    print(f"latency N={len(lats)}")
    print(f"  min  : {min(lats):.2f} s")
    print(f"  p50  : {pct(0.50):.2f} s")
    print(f"  p90  : {pct(0.90):.2f} s")
    print(f"  p95  : {pct(0.95):.2f} s")
    print(f"  p99  : {pct(0.99):.2f} s")
    print(f"  max  : {max(lats):.2f} s")
    print(f"  mean : {sum(lats)/len(lats):.2f} s")
else:
    print("no latency samples captured")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 14. Error taxonomy
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Error taxonomy — what does the model actually get wrong?

For each field, inspect up to 3 failure examples. This is where
you find *patterns* — is the model confused by handwritten digits,
foreign currencies, multi-line vendor names, stacked totals, etc.?

Patterns discovered here go straight into the QLoRA training data
recipe: over-sample documents exhibiting the failure mode so the
fine-tune teaches the model to handle it.
"""))


CELLS.append(code("""
MAX_EXAMPLES_PER_FIELD = 3

for field in SCALAR_FIELDS:
    examples = []
    for r in results:
        if len(examples) >= MAX_EXAMPLES_PER_FIELD:
            break
        pred = (r.get("parsed") or {}).get(field) if r.get("parsed") else None
        gt = (r.get("gt") or {}).get(field)
        cat = classify(pred, gt, field)
        if cat in ("wrong", "miss", "hallucination"):
            examples.append((cat, pred, gt))
    if not examples:
        continue
    print(f"\\n=== {field} — failure examples ===")
    for cat, pred, gt in examples:
        print(f"  [{cat}]  pred={pred!r:<30}  gt={gt!r}")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 15. Auto-generated conclusions
# ─────────────────────────────────────────────────────────────────────────────
CELLS.append(md("""
## Auto-generated conclusions

Ranks fields from strongest to weakest by F1 and suggests fine-tuning
priorities. Use this as the starting point for the QLoRA data recipe;
fill in the marked TODOs with patterns you noticed in the error
taxonomy above.
"""))


CELLS.append(code("""
sorted_metrics = sorted(field_metrics, key=lambda m: m[\"f1\"], reverse=True)

# Partition: strong (F1 >= 0.8), mid (0.5..0.8), weak (<0.5)
strong = [m for m in sorted_metrics if m[\"f1\"] >= 0.8]
mid    = [m for m in sorted_metrics if 0.5 <= m[\"f1\"] < 0.8]
weak   = [m for m in sorted_metrics if m[\"f1\"] < 0.5]

print(\"STRONG (F1 >= 0.80) — SKIP for fine-tuning, already solid:\")
for m in strong:
    print(f\"  - {m['field']:<16}  F1={m['f1']:.2f}  P={m['precision']:.2f}  R={m['recall']:.2f}\")
if not strong:
    print(\"  (none)\")

print(\"\\nMID (0.50 <= F1 < 0.80) — include in QLoRA, moderate weight:\")
for m in mid:
    print(f\"  - {m['field']:<16}  F1={m['f1']:.2f}  P={m['precision']:.2f}  R={m['recall']:.2f}\")
if not mid:
    print(\"  (none)\")

print(\"\\nWEAK (F1 < 0.50) — primary QLoRA fine-tuning targets:\")
for m in weak:
    # Diagnose the DOMINANT failure mode
    buckets = {k: m[k] for k in (\"miss\", \"wrong\", \"hallucination\")}
    top_mode = max(buckets, key=buckets.get) if sum(buckets.values()) else None
    hint = {
        \"miss\": \"model returns null too often — needs more positive examples\",
        \"wrong\": \"model returns incorrect values — needs layout/visual diversity\",
        \"hallucination\": \"model fabricates values — prompt may need tightening BEFORE fine-tune\",
    }.get(top_mode, \"mixed failure modes\")
    print(f\"  - {m['field']:<16}  F1={m['f1']:.2f}  dominant={top_mode}  → {hint}\")
if not weak:
    print(\"  (none — model is usable zero-shot, consider skipping fine-tune entirely)\")

# Parse robustness flag
if parse_fail / max(len(results), 1) > 0.05:
    print(\"\\n⚠  JSON parse failure > 5% — fix the PROMPT before fine-tuning.\")
    print(\"   Grammar-constrained decoding or output schema (outlines / guidance) \")
    print(\"   will give more leverage than a LoRA adapter here.\")

print(\"\\nQLoRA data recipe suggestion:\")
if weak:
    print(\"  - Curate ~50-100 examples per weak field where the model currently fails\")
    print(\"  - Stratify by failure mode (missing value, wrong value, hallucination)\")
    print(\"  - Keep a held-out CORD + SROIE split with no overlap\")
print(\"  - Freeze on strong fields: include them in training but with lower weight\")
print(\"    to avoid catastrophic forgetting on things already working\")
print(\"  - Target rank r=16 or r=32; start from the baseline Qwen2-VL-7B; train \")
print(\"    for 2-4 epochs max — QLoRA overfits fast on small document corpora\")
"""))


# ─────────────────────────────────────────────────────────────────────────────
# 16. Final assemble
# ─────────────────────────────────────────────────────────────────────────────

notebook = {
    "cells": CELLS,
    "metadata": {
        "kernelspec": {
            "display_name": ".venv",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11.4",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=1))
print(f"wrote {NOTEBOOK_PATH}  ·  {len(CELLS)} cells")
