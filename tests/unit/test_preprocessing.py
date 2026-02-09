import os

import numpy as np
import pytest

from src.backend.ingestion.preprocessing import Preprocessing


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
SAMPLE_PDF = os.path.join(FIXTURES_DIR, "sample_invoice.pdf")


class TestPreprocessing:
    def setup_method(self):
        self.preprocessor = Preprocessing()

    def test_pdf_to_images_returns_list_of_arrays(self):
        images = self.preprocessor.convert_pdf_to_images(SAMPLE_PDF)
        assert isinstance(images, list)
        assert len(images) > 0
        assert isinstance(images[0], np.ndarray)

    def test_deskew_preserves_shape(self):
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        img[40:60, 20:180] = 255
        result = self.preprocessor.deskew_image(img)
        assert result.shape[0] > 0
        assert result.shape[1] > 0

    def test_denoise_reduces_std(self):
        rng = np.random.default_rng(42)
        noisy = rng.integers(0, 255, (100, 100), dtype=np.uint8)
        denoised = self.preprocessor.denoise_image(noisy)
        assert denoised.std() < noisy.std()

    def test_grayscale_is_2d(self):
        color_img = np.zeros((100, 100, 3), dtype=np.uint8)
        color_img[:, :, 0] = 200
        gray = self.preprocessor.to_grayscale(color_img)
        assert len(gray.shape) == 2

    def test_preprocess_document_returns_pages(self):
        pages = self.preprocessor.preprocess_document(SAMPLE_PDF)
        assert isinstance(pages, list)
        assert len(pages) > 0
        page = pages[0]
        assert hasattr(page, "original")
        assert hasattr(page, "processed")
        assert isinstance(page.processed, np.ndarray)
        assert len(page.processed.shape) == 2
