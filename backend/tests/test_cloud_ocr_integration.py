"""Live-provider smoke tests. They are opt-in because they consume cloud quota."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PIL import Image, ImageDraw

from app.services.documents import cloud_ocr


def _enabled(variable: str) -> bool:
    return os.getenv(variable, "").strip().lower() in {"1", "true", "yes"}


@pytest.mark.integration
@pytest.mark.cloud
class CloudOCRIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        _enabled("RUN_GOOGLE_VISION_OCR_INTEGRATION") and bool(cloud_ocr.GOOGLE_VISION_API_KEY),
        "Set RUN_GOOGLE_VISION_OCR_INTEGRATION=1 and GOOGLE_VISION_API_KEY to run the live Google Vision check.",
    )
    def test_google_vision_reads_a_real_uploaded_image(self):
        with TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            source = Path(temporary_directory) / "ocr-smoke.png"
            image = Image.new("RGB", (600, 160), "white")
            ImageDraw.Draw(image).text((30, 60), "NEXORA OCR 2026", fill="black")
            image.save(source)
            text = cloud_ocr._google_vision(source, "image/png")

        self.assertIn("NEXORA", text.upper())

    @unittest.skipUnless(
        _enabled("RUN_AZURE_OCR_INTEGRATION")
        and bool(cloud_ocr.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT)
        and bool(cloud_ocr.AZURE_DOCUMENT_INTELLIGENCE_KEY),
        "Set RUN_AZURE_OCR_INTEGRATION=1 and Azure OCR credentials to run the live Azure check.",
    )
    def test_azure_reads_a_real_uploaded_image(self):
        with TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            source = Path(temporary_directory) / "ocr-smoke.png"
            image = Image.new("RGB", (600, 160), "white")
            ImageDraw.Draw(image).text((30, 60), "NEXORA OCR 2026", fill="black")
            image.save(source)
            text = cloud_ocr._azure_document_intelligence(source, "image/png")

        self.assertIn("NEXORA", text.upper())
