from dataclasses import dataclass

import cv2
import numpy as np
from pdf2image import convert_from_path


@dataclass
class PreprocessedPage:
    page_number: int
    original: np.ndarray
    processed: np.ndarray


class Preprocessing:
    def convert_pdf_to_images(self, pdf_path: str) -> list[np.ndarray]:
        pil_images = convert_from_path(pdf_path, dpi=300)
        return [np.array(img) for img in pil_images]

    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return image

    def deskew_image(self, image: np.ndarray) -> np.ndarray:
        gray = self.to_grayscale(image) if len(image.shape) == 3 else image
        coords = np.column_stack(np.where(gray > 0))
        if len(coords) < 5:
            return image
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )

    def denoise_image(self, image: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(image, (5, 5), 0)

    def preprocess_document(self, pdf_path: str) -> list[PreprocessedPage]:
        images = self.convert_pdf_to_images(pdf_path)
        pages = []
        for i, img in enumerate(images):
            gray = self.to_grayscale(img)
            denoised = self.denoise_image(gray)
            deskewed = self.deskew_image(denoised)
            pages.append(PreprocessedPage(
                page_number=i + 1,
                original=img,
                processed=deskewed,
            ))
        return pages
