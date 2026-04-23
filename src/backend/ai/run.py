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

def run_single():
    for dataset in DATASETS:
        path = Path(dataset)

        if not path.exists():
            raise ValueError(f"Dataset not found: {dataset}")

        for file_path in path.iterdir():
            if not file_path.is_file():
                continue

            result = process_document(str(file_path))
            print(result)
            save_result(result)

if __name__ == "__main__":
    run_single()

