import pytesseract
from PIL import Image


def run_ocr(file_path: str) -> str:
    image = Image.open(file_path)
    text = pytesseract.image_to_string(image)
    return text