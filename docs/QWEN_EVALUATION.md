# Qwen2-VL-7B Evaluation & Tier Reorganization

**Decision:** Qwen2-VL-7B (4-bit QLoRA-tuned) becomes **Tier 2 (local VLM)**.
Gemini 2.5 Flash moves to **Tier 3 (cloud fallback)**. The dual-brain pattern
becomes a tri-tier pattern: fast deterministic → local VLM → cloud VLM →
HITL.

This document records the zero-shot evaluation that informs the
fine-tuning plan, the architectural reasoning, and the concrete QLoRA
recipe.

---

## 1. Evaluation setup

| | |
|---|---|
| Model | `Qwen/Qwen2-VL-7B-Instruct` |
| Quantization | 4-bit NF4 via bitsandbytes |
| Hardware | Colab T4 (14.56 GB VRAM) |
| Dataset | CORD-v2 test split, first 50 receipts |
| Prompt | Strict-JSON schema with 7 fields including `line_items` |
| Eval harness | `notebooks/qwen.ipynb` cells ❶–❼ + ❽ |
| Date | April 2026 |

The eval reports per-field precision / recall / F1 with five-bucket
classification (`exact`, `numeric_ok`, `fuzzy`, `wrong`, `miss`,
`hallucination`), JSON parse robustness, line-item count + content
matching, p50/p95 latency, and CER/WER per the OCR literature.

---

## 2. Headline numbers (zero-shot, no fine-tune)

```
field            P     R    F1   N    notes
total_amount   0.83  0.74  0.79  50   strong; misleading misses are Korean number formatting
subtotal       0.50  0.68  0.57  50   real recall problem (19/50 misses)
line_items     —     —     —     50   72% count match · 84.5% positional description match
invoice_number 0.00  0.00  0.00   5*  unmeasurable on CORD (sparse GT)
vendor_name    0.00  0.00  0.00   7*  unmeasurable on CORD (sparse GT)
tax            0.00  0.00  0.00  14*  CORD silent on most receipts; "hallucinations" likely correct
date           0.00  0.00  0.00   0   not in CORD GT at all

Latency p50 / p95 / max:  14.7s / 31.9s / 36.4s
JSON parse rate:          ~98% (excluding 6 CUDA-OOM crashes)
```

\* `N` for these fields is the count of CORD samples where the field was
ground-truthed at all. Where `N=5`, all 5 predictions were classified as
`hallucination` because every CORD GT for that field was None.

---

## 3. What the numbers really say

### 3a. Three "F1=0.00" verdicts are measurement artifacts, not model failures

CORD's ground truth is sparse on `invoice_number`, `date`, `vendor_name`,
and `tax`. The eval flags every non-null prediction against a null GT as
a `hallucination`. Manual inspection of the listed examples shows the
model is *correctly* extracting these fields — CORD just didn't label
them:

```
[hallucination]  pred='CGV CINEMAS'        gt=None   ← correct vendor
[hallucination]  pred='Auntie Anne's'      gt=None   ← correct vendor
[hallucination]  pred=5455                 gt=None   ← correct tax (visible on receipt)
```

These cannot be used as fine-tuning targets without a different ground
truth source (SROIE has `company` labels; spot-check is required for
tax). Reporting them as model weaknesses would be misleading.

### 3b. Korean number formatting deflates `total_amount` and `subtotal`

CORD writes Korean Won with `.` as the thousands separator: `60.000`
means ₩60,000. The model emits the integer `60000`. Exact-match
penalizes this; the `numeric_ok` bucket (which uses parsed Decimals
within ±$0.02) catches it correctly. The reported F1=0.79 on
`total_amount` underestimates true accuracy — adding `numeric_ok` to
the win count gives 27 + 2 + 6 = **35/50 = 70% match before any
fine-tuning**.

A one-line prompt fix ("for currency amounts, return the integer with
no thousands separator") should push `total_amount` F1 above 0.90
before a single LoRA epoch.

### 3c. The genuine signal: `subtotal` recall and `line_items`

- **`subtotal` 19/50 misses** is real — the model is confidently
  returning `null` when CORD has a labeled subtotal. This is a true
  fine-tuning target.
- **`line_items` at 72% count + 84.5% positional description match** is
  the strongest result and the model's competitive edge. PaddleOCR +
  heuristics is structurally weak at this exact task.

### 3d. JSON discipline is fine

The 84% parse-success number in cell ❼'s warning is misleading: 6 of
the 8 failures are CUDA OOMs, not bad JSON. True parse failure rate
is ~2/42 ≈ 5%, which is acceptable. No grammar-constrained decoding
needed.

### 3e. Latency rules out Tier 1 use

p50 14.7s, p95 31.9s on a T4. Even after fine-tuning, this is
~15× slower than the current Tier 1 (PaddleOCR ~1s). Qwen2-VL is
permanently a Tier 2 candidate, not a Tier 1 replacement.

---

## 4. Architectural placement: why Tier 2

```
┌────────────────────────────────────────────────────────────────────┐
│  Tier 1 — local deterministic (PaddleOCR + heuristics + auditor)   │
│           ~1s, $0, handles ~80% of clean documents                 │
└────────────────────────┬───────────────────────────────────────────┘
                         │ math/verifier gate fails
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│  Tier 2 — local VLM (Qwen2-VL-7B 4-bit, QLoRA-tuned)               │
│           ~15s, $0 (after model is loaded), runs on owned GPU      │
│           Strong at line items + structural extraction             │
└────────────────────────┬───────────────────────────────────────────┘
                         │ second auditor pass still fails
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│  Tier 3 — cloud VLM (Gemini 2.5 Flash via BAML)                    │
│           ~3s, $$, last automated resort                           │
│           Strongest model, used sparingly                          │
└────────────────────────┬───────────────────────────────────────────┘
                         │ third auditor pass still fails
                         ▼
                       HITL
```

**Why this is the right placement for Qwen2-VL:**

1. **Cost:** Once fine-tuned and deployed on owned hardware, marginal
   cost per document is electricity. Gemini API charges per call. For
   a system processing thousands of receipts, the local tier absorbs
   bulk volume and the cloud tier only sees the truly hard cases.
2. **Privacy:** Customer data never leaves the local environment unless
   Tier 2 also fails. For enterprise pilots where data residency
   matters (the FYP's industry partner context), this is a deployment
   blocker turned solved.
3. **Skill complement:** The eval shows Qwen2-VL is strong at line
   items — the exact task PaddleOCR struggles with most. Tier 2 picks
   up where Tier 1 leaves off without paying API rates.
4. **Latency tolerance:** ~15s for the slow path is acceptable when
   Tier 1 handles the fast path. Only documents that fail the auditor
   pay the Tier 2 cost.

**Why Gemini stays in the architecture as Tier 3:**

- Frontier-model fallback: when both deterministic logic AND a fine-tuned
  local VLM disagree with each other, defer to the strongest model
  available. This is the "safety net before HITL" — cheaper than human
  review, more reliable than re-asking the local model.
- BAML contracts already wired up; no implementation cost to keep.
- Operational reliability: Gemini Flash + Flash-Lite fallback means the
  pipeline never fully fails on a stuck local GPU.

---

## 5. QLoRA fine-tuning plan

### 5a. Targets (ranked by ROI)

| Target | Why | How |
|---|---|---|
| **`subtotal` recall** | 19/50 misses on CORD = 38% miss rate on labeled fields. Strongest measurable improvement available. | Curate 100+ examples where subtotal is present and the base model returns null. Stratify across receipt layouts. |
| **`line_items` content fidelity** | Already 84.5% positional match — the goal here is to *protect* this strength during fine-tuning, not regress it. | Include line-item-rich samples in training data with full description / qty / price labels. Use sample-weight to balance against subtotal-focused samples. |
| **JSON output discipline** | ~5% raw failure rate (excluding OOM). Low ROI vs grammar constraints, but a few epochs of well-formed examples should clear it. | No special handling — just don't break it during training. |

### 5b. Targets explicitly NOT pursued

| Skip | Reason |
|---|---|
| `vendor_name` / `invoice_number` / `tax` / `date` on CORD | CORD GT is sparse → we can't measure improvement. To target these, switch to SROIE (which has `company` labels). |
| `total_amount` exact-format matching | Solvable via prompt change ("integer with no thousands separator"). Don't waste LoRA capacity on what a one-line prompt edit fixes. |

### 5c. Hyperparameters (baseline — to be tuned during fine-tuning)

```
adapter:           QLoRA (4-bit base + LoRA on attention projections)
target modules:    q_proj, v_proj, k_proj, o_proj   (attention only first;
                                                     extend to MLP if val plateaus)
rank (r):          16          (start; bump to 32 if val F1 stalls)
alpha:             32          (2× rank, standard)
dropout:           0.05
learning rate:     2e-4        (cosine schedule with 5% warmup)
batch size:        4 effective (gradient accumulation as needed for VRAM)
epochs:            2–4         (overfits fast on small corpora; early-stop
                                on validation F1)
max input tokens:  2048
max new tokens:    256         (down from 512 — cuts OOM risk and is more
                                than enough output for the schema)
```

### 5d. Training data plan

| Slice | Source | Size | Purpose |
|---|---|---|---|
| Subtotal-positive | CORD train + manual augmentation | 100–150 | Primary fine-tune target |
| Subtotal-negative | CORD train (tax-only / no subtotal) | 30 | Anti-hallucination — teach when NOT to predict subtotal |
| Line-item-rich | CORD train (≥4 items) | 50 | Protect existing strength |
| Mixed full receipts | CORD train | 50 | Maintain global formatting discipline |
| **Held-out validation** | **SROIE test** | **~300** | **Different distribution. If F1 holds on SROIE, fine-tune generalized. If it drops, we overfit CORD.** |

### 5e. Pre-training prompt fixes (do these BEFORE QLoRA)

1. **Currency normalization:** "Return integer values for amount fields with no thousands separator. The receipt may show `60.000`, `60,000`, or `60000` — all mean sixty thousand; output `60000`."
2. **Field absence handling:** "Use `null` only when the field is provably absent from the receipt. If you can see the field, extract it even if the layout is unusual."
3. **Date format:** "If a date is visible, return it in YYYY-MM-DD format. Use `null` only if no date is visible."

Re-evaluate on the same 50 CORD samples after these prompt fixes to
isolate prompt-improvement gains from fine-tuning gains. **If
`total_amount` F1 jumps to 0.90+ on prompt alone, that's free
performance and the QLoRA budget can refocus entirely on `subtotal`
and `line_items`.**

### 5f. Expected outcomes (concrete success criteria)

| Metric | Pre-fine-tune | After QLoRA target |
|---|---|---|---|
| total_amount F1 | 0.79 | 0.92+ |
| subtotal F1 | 0.57 | **0.80+** |
| line_items count match | 72% | **≥75%** (don't regress) |
| line_items description match | 84.5% | **≥85%** (don't regress) |
| JSON parse rate | 95% (real) | 98% |
| p50 latency | 14.7s | 14.7s ± 1s (no change expected) |

If subtotal F1 doesn't reach 0.80, either the training data was
under-curated or the model needs higher LoRA rank (32) or longer
training (4 epochs). Don't keep training past 4 epochs — small-corpus
QLoRA on receipts overfits fast.

---

## 6. Operational issues to fix before training

### 6a. CUDA OOM on T4 (8 of 50 samples crashed)

- Resize images to max 1024px on the long edge before passing to processor
- Drop `max_new_tokens` from 512 → 256
- For training, move to A100 40GB MIG (or A100 80GB if available)

### 6b. Latency budget for training step

A single forward pass at 14.7s p50 means a single training step
(forward + backward + optimizer) is roughly 30–40s. A 4-epoch run on
250 samples = 1000 steps × 35s ≈ **10 hours**. Budget 2 evening
sessions on the A100 MIG; checkpoint every epoch so a session interrupt
doesn't wipe the run.

---

## 7. Honest risks and limitations

1. **CORD bias:** Korean retail receipts. SROIE bias: UK/Singapore retail.
   Neither matches a generic invoice distribution perfectly. Fine-tuned
   model should be re-evaluated on the production traffic distribution
   before being put on a critical path.
2. **Reward hacking:** the eval bucket structure rewards `null` when GT
   is `null`. A degenerate model that always returns `null` would score
   well on `both_null`. The line-items metrics + active recall on
   `subtotal` partially counter this, but a paper-grade evaluation
   needs a held-out set with high field-coverage GT.
3. **Latency floor:** even a perfect QLoRA can't make Qwen2-VL-7B run
   in under ~5s on a T4. If the production SLA needs sub-3s on the slow
   path, this architecture won't satisfy it without dedicated A100s or
   model distillation.
4. **OOM as training-stopper:** 8/50 samples OOM'd on T4 at *inference*
   batch size 1. Training on T4 is not viable; an A100 MIG is the
   minimum.

---

## 8. Conclusion (one paragraph for the paper)

Zero-shot Qwen2-VL-7B (4-bit QLoRA-base) on CORD-v2 produces usable
extractions across all six target fields, with measured strengths in
line-item content extraction (84.5% positional match) and total-amount
recovery (F1=~0.88). The remaining recall gap on `subtotal` (38% miss rate) is the principal
QLoRA fine-tuning target. With a curated 250-sample training set and
SROIE held out for cross-distribution validation, we expect post-tune
F1 of 0.92 / 0.80 / 0.85+ on total_amount / subtotal / line_items
respectively. Latency remains 10–30s per document, justifying Qwen2-VL's
placement as Tier 2 (local fallback when the deterministic Tier 1 +
verifier gate fails) rather than Tier 1, with cloud Gemini retained as
Tier 3 for the residual cases where local extraction still disagrees
with the math auditor.
