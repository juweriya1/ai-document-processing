"""train_qlora.py — QLoRA fine-tuning of Qwen2-VL-7B-Instruct on SROIE (English receipts).

Designed for an A100 80GB. Typical run: ~500 steps, ~1 hour.

Usage:
    python scripts/train_qlora.py
    python scripts/train_qlora.py --max_steps 1000 --learning_rate 1e-4
    python scripts/train_qlora.py --output_dir adapters/run2
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = "adapters/qwen2vl_sroie"
DEFAULT_MAX_STEPS = 500
DEFAULT_LR = 2e-4
DEFAULT_BATCH_SIZE = 1
DEFAULT_MODEL_NAME = "Qwen/Qwen2-VL-7B-Instruct"

LORA_TARGET_MODULES = [
    "q_proj", "v_proj", "k_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

# Must exactly match VLMExtractor.EXTRACTION_PROMPT so train/inference distributions align
EXTRACTION_PROMPT = (
    "You are a financial document extraction assistant. "
    "Extract the following fields from this document image. "
    "Return ONLY valid JSON with exactly these keys (use null for missing fields):\n"
    "{\n"
    '  "invoice_number": "string or null",\n'
    '  "date": "YYYY-MM-DD or null",\n'
    '  "vendor_name": "string or null",\n'
    '  "total_amount": "numeric string or null",\n'
    '  "subtotal": "numeric string or null",\n'
    '  "tax": "numeric string or null",\n'
    '  "line_items": [\n'
    '    {"description": "string", "quantity": 0.0, "unit_price": 0.0, "total": 0.0}\n'
    "  ]\n"
    "}"
)


# ---------------------------------------------------------------------------
# Ground truth parsers
# ---------------------------------------------------------------------------

def parse_sroie_ground_truth(row: dict[str, Any]) -> dict[str, Any]:
    """Parse a SROIE row into a canonical GT dict.

    SROIE provides: company→vendor_name, date→date, total→total_amount.
    invoice_number, subtotal, tax, and line_items are always None / [].
    """
    def _clean(v: Any) -> str | None:
        s = str(v).strip() if v else None
        return s if s else None

    return {
        "invoice_number": None,
        "date": _clean(row.get("date")),
        "vendor_name": _clean(row.get("company")),
        "total_amount": _clean(row.get("total")),
        "subtotal": None,
        "tax": None,
        "line_items": [],
    }


def _empty_gt() -> dict[str, Any]:
    return {
        "invoice_number": None, "date": None, "vendor_name": None,
        "total_amount": None, "subtotal": None, "tax": None, "line_items": [],
    }


def gt_dict_to_json_string(gt: dict[str, Any]) -> str:
    """Serialise a canonical GT dict to the JSON string the model must output.

    Ensures all seven scalar keys are present (None → null), and line_items
    is always a list. Quantities/prices are cast to float.
    """
    normalised = {
        "invoice_number": gt.get("invoice_number"),
        "date": gt.get("date"),
        "vendor_name": gt.get("vendor_name"),
        "total_amount": gt.get("total_amount"),
        "subtotal": gt.get("subtotal"),
        "tax": gt.get("tax"),
        "line_items": [],
    }
    for item in gt.get("line_items") or []:
        if not isinstance(item, dict):
            continue
        normalised["line_items"].append({
            "description": str(item.get("description", "")),
            "quantity": float(item.get("quantity") or 0.0),
            "unit_price": float(item.get("unit_price") or 0.0),
            "total": float(item.get("total") or 0.0),
        })
    return json.dumps(normalised, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Dataset builders
# ---------------------------------------------------------------------------

def _row_to_example(pil_image: Any, gt_dict: dict[str, Any]) -> dict[str, Any]:
    """Convert a PIL image + GT dict into a two-turn Qwen2-VL conversation dict."""
    gt_str = gt_dict_to_json_string(gt_dict)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        },
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": gt_str},
            ],
        },
    ]
    return {"messages": messages, "images": [pil_image]}


def build_sroie_dataset():
    """Load SROIE train split (English receipts) and convert to conversation examples."""
    from datasets import load_dataset  # type: ignore[import]

    logger.info("Loading SROIE train split …")
    dataset = None
    for ds_id, kwargs in [
        ("mychen76/invoices-and-receipts_ocr_v1", {"split": "train"}),
        ("darentang/sroie", {"config_name": "original", "split": "train", "trust_remote_code": True}),
    ]:
        try:
            dataset = load_dataset(ds_id, **kwargs)
            logger.info("Loaded SROIE from %s", ds_id)
            break
        except Exception as e:
            logger.warning("Could not load %s: %s", ds_id, e)

    if dataset is None:
        raise RuntimeError("No SROIE-compatible dataset could be loaded. Check network access.")

    examples = []
    skipped = 0
    for row in dataset:
        pil_image = row.get("image") or row.get("img")
        if pil_image is None:
            skipped += 1
            continue
        gt = parse_sroie_ground_truth(row)
        examples.append(_row_to_example(pil_image, gt))
    logger.info("SROIE: %d examples loaded, %d skipped", len(examples), skipped)
    return examples


def build_training_dataset():
    """Build SROIE-only training dataset (English receipts).

    Returns a HuggingFace Dataset with columns: messages, images.
    """
    import random
    from datasets import Dataset  # type: ignore[import]

    examples = build_sroie_dataset()
    random.seed(42)
    random.shuffle(examples)
    logger.info("Training dataset: %d examples", len(examples))
    return Dataset.from_list(examples)


# ---------------------------------------------------------------------------
# Model / training setup
# ---------------------------------------------------------------------------

def load_base_model_4bit(model_name: str):
    """Load Qwen2-VL-7B-Instruct in 4-bit bitsandbytes quantisation.

    Uses the same BitsAndBytesConfig as VLMExtractor._load_model so that
    adapter weights are compatible at inference time.

    Returns:
        (model, processor)
    """
    import torch
    from transformers import (  # type: ignore[import]
        AutoProcessor,
        BitsAndBytesConfig,
        Qwen2VLForConditionalGeneration,
    )

    logger.info("Loading base model: %s (4-bit)", model_name)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    return model, processor


def apply_lora(model, r: int = LORA_R, alpha: int = LORA_ALPHA, dropout: float = LORA_DROPOUT):
    """Wrap model with PEFT LoraConfig targeting LORA_TARGET_MODULES.

    Returns the peft model with gradients enabled only for LoRA parameters.
    """
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training  # type: ignore[import]

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora_config = LoraConfig(
        r=r,
        lora_alpha=alpha,
        lora_dropout=dropout,
        target_modules=LORA_TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


def make_collator(processor):
    """Return a data-collation callable for SFTTrainer.

    Applies processor.apply_chat_template, tokenises the combined user+assistant
    turn, and masks user-turn tokens in labels (loss computed only on assistant
    response tokens).

    Returns:
        Callable[[list[dict]], dict]
    """
    import torch

    def collate(examples: list[dict]) -> dict:
        batch_messages = [ex["messages"] for ex in examples]
        batch_images = [ex["images"] for ex in examples]

        texts = [
            processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
            for msgs in batch_messages
        ]

        try:
            from qwen_vl_utils import process_vision_info  # type: ignore[import]
            image_inputs_list = []
            video_inputs_list = []
            for msgs in batch_messages:
                img_in, vid_in = process_vision_info(msgs)
                image_inputs_list.append(img_in)
                video_inputs_list.append(vid_in)
            # Flatten for batch processor call
            all_images = [img for imgs in image_inputs_list for img in (imgs or [])]
            inputs = processor(
                text=texts,
                images=all_images if all_images else None,
                padding=True,
                return_tensors="pt",
            )
        except ImportError:
            flat_images = [img for imgs in batch_images for img in imgs]
            inputs = processor(
                text=texts,
                images=flat_images if flat_images else None,
                padding=True,
                return_tensors="pt",
            )

        # Build labels: copy input_ids, mask pad tokens and user-turn tokens with -100
        labels = inputs["input_ids"].clone()
        labels[labels == processor.tokenizer.pad_token_id] = -100

        # Mask everything before the assistant turn by finding the assistant token boundary
        for i, msgs in enumerate(batch_messages):
            user_text = processor.apply_chat_template(
                [msgs[0]], tokenize=False, add_generation_prompt=True
            )
            user_tokens = processor.tokenizer(user_text, return_tensors="pt")["input_ids"]
            user_len = user_tokens.shape[1]
            labels[i, :user_len] = -100

        inputs["labels"] = labels
        return inputs

    return collate


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------

def train(
    output_dir: str,
    max_steps: int,
    learning_rate: float,
    batch_size: int,
    model_name: str = DEFAULT_MODEL_NAME,
) -> None:
    """Orchestrate full QLoRA training run.

    Steps:
        1. Build combined CORD + SROIE dataset
        2. Load 4-bit base model + apply LoRA
        3. Configure SFTTrainer with gradient checkpointing, bf16, grad accum
        4. Train for max_steps steps
        5. Save adapter weights to output_dir
    """
    from transformers import TrainingArguments  # type: ignore[import]
    from trl import SFTTrainer  # type: ignore[import]

    dataset = build_training_dataset()
    model, processor = load_base_model_4bit(model_name)
    model = apply_lora(model)

    training_args = TrainingArguments(
        output_dir=output_dir,
        max_steps=max_steps,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        learning_rate=learning_rate,
        bf16=True,
        gradient_checkpointing=True,
        dataloader_num_workers=0,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        remove_unused_columns=False,
        warmup_steps=50,
        lr_scheduler_type="cosine",
        optim="paged_adamw_8bit",
        report_to="none",
    )

    collator = make_collator(processor)

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
        dataset_text_field=None,
        max_seq_length=1024,
        tokenizer=processor.tokenizer,
    )

    logger.info("Starting training: %d steps on %d examples", max_steps, len(dataset))
    trainer.train()

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)
    logger.info("Adapter weights saved to %s", output_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QLoRA fine-tuning of Qwen2-VL-7B-Instruct on SROIE (English receipts)."
    )
    parser.add_argument("--output_dir", default=DEFAULT_OUTPUT_DIR,
                        help="Directory to write adapter weights (default: %(default)s)")
    parser.add_argument("--max_steps", type=int, default=DEFAULT_MAX_STEPS,
                        help="Total training steps (default: %(default)s)")
    parser.add_argument("--learning_rate", type=float, default=DEFAULT_LR,
                        help="AdamW learning rate (default: %(default)s)")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="per_device_train_batch_size (default: %(default)s; keep 1 on MIG)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train(
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
