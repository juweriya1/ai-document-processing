from pathlib import Path
import json
from datetime import datetime

from backend.ai.ocr import run_ocr
from backend.ai.extract import extract_fields


SAMPLES_DIR = Path("src/backend/ai/data/samples")
OUTPUT_FILE = Path("src/backend/ai/outputs/tesseract_v0.jsonl")


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
    # today: only one file exists, so this is safe
    files = list(SAMPLES_DIR.glob("*"))

    if not files:
        raise ValueError("No sample files found")

    file_path = str(files[0])

    result = process_document(file_path)

    print(result)
    save_result(result)


if __name__ == "__main__":
    run_single()