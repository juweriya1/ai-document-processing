# AI Pipeline — Step 1 (Raw OCR)

This is the starting point of the document processing system.

Pipeline:
Image → OCR → raw text

No extraction logic yet.

## Setup

Install Python dependencies:

pip install -r src/backend/ai/requirements.txt

---

## Install Tesseract OCR

### Mac
brew install tesseract

### Ubuntu / Linux
sudo apt install tesseract-ocr

### Windows

1. Download installer from:
https://github.com/tesseract-ocr/tesseract

2. Install it (default path is usually fine)

3. Add Tesseract to PATH:
   - Open "Environment Variables"
   - Edit `Path`
   - Add something like:
     C:\Program Files\Tesseract-OCR

4. Verify:
tesseract --version

---

## Run

PYTHONPATH=src python src/backend/ai/run.py