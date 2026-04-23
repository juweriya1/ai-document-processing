import sys
from pathlib import Path

# THIS is the key fix
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend.ai.run import process_document

pdf_path = "sample.pdf"
print(process_document(pdf_path))