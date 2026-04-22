from pathlib import Path
import json
from datetime import datetime

from backend.ai.ocr import run_ocr
from backend.ai.extract import extract_fields


DATASETS = [
    "src/backend/ai/data/local_receipts",
    "src/backend/ai/data/sroie_receipts",
]

OUTPUT_FILE = Path("src/backend/ai/outputs/tesseract_eval_with_regex_extract.jsonl")


def process_document(file_path: str):
    text = run_ocr(file_path)
    fields = extract_fields(text)

    return {
        "file": file_path,
        "fields": fields,
        "raw_text": text
    }


def save_result(result: dict):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now().isoformat(),
        **result
    }

    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_dataset(dataset_path: str):
    folder = Path(dataset_path)
    files = list(folder.glob("*"))

    if not files:
        raise ValueError(f"No files found in {dataset_path}")

    print(f"\nRunning Tesseract eval on: {dataset_path}")
    print(f"Files: {len(files)}")

    for file_path in files:
        result = process_document(str(file_path))
        print(result["file"])
        save_result(result)


if __name__ == "__main__":
    for dataset in DATASETS:
        run_dataset(dataset)