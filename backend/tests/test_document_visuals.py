import base64
import io
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.services.document_visuals import source_region, VisualUnavailable, wants_document_image, _locate, _crop
from app.api.routes.documents import get_source_region, SourceRegionRequest
from app.services import cloud_ocr


def pdf_with_text(path, rotation=0):
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=500)
    page = writer.add_blank_page(width=400, height=500)
    if rotation:
        page.rotate(rotation)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 14 Tf 40 300 Td (Insurance commitments payment coverage) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as output:
        writer.write(output)


def test_original_pdf_region_has_correct_page_and_real_png(tmp_path):
    path = tmp_path / "original.pdf"
    pdf_with_text(path)
    result = source_region(path, "application/pdf", "Show image of insurance commitments", "Insurance commitments payment coverage")
    assert result["page"] == 2
    png = base64.b64decode(result["image"].split(",")[1])
    image = Image.open(io.BytesIO(png))
    assert image.size == (result["width"], result["height"])
    assert image.height < 500
    assert image.convert("L").getextrema()[0] < 100


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_page_crop_contains_real_text(tmp_path, rotation):
    path = tmp_path / "original.pdf"
    pdf_with_text(path, rotation)
    result = source_region(path, "application/pdf", "Show insurance commitments image", "Insurance commitments payment coverage")
    image = Image.open(io.BytesIO(base64.b64decode(result["image"].split(",")[1])))
    assert image.convert("L").getextrema()[0] < 100


def test_no_guess_when_requested_region_is_missing(tmp_path):
    path = tmp_path / "original.pdf"
    pdf_with_text(path)
    with pytest.raises(VisualUnavailable):
        source_region(path, "application/pdf", "Show image of refund cancellation", "Insurance commitments payment coverage")


def test_source_support_is_required_and_persian_normalized():
    words = [("بيمه", (10, 20, 30, 40)), ("تعهدات", (35, 20, 55, 40)), ("پرداخت", (60, 20, 90, 40))]
    assert _locate(words, "عکس جدول تعهدات بیمه را نشان بده", "بیمه تعهدات پرداخت")
    assert not _locate(words, "عکس تعهدات بیمه", "موضوع کاملا متفاوت")
    assert wants_document_image("عکس جدول تعهدات بیمه را نشان بده")
    assert not wants_document_image("تعهدات بیمه چیست؟")
    assert not wants_document_image("What is image processing?")
    assert _locate(words, "تصویر بیمه را بفرست", "بیمه تعهدات پرداخت")


def test_crop_expands_to_real_table_grid():
    image = Image.new("RGB", (400, 500), "white")
    draw = ImageDraw.Draw(image)
    for y in [100, 150, 200, 250, 300]:
        draw.line((50, y, 350, y), fill="black")
    for x in [50, 200, 350]:
        draw.line((x, 100, x, 300), fill="black")
    result = _crop(image, (90, 160, 220, 190))
    assert result["bounds"][1] < 100
    assert result["bounds"][3] > 300


def test_saved_scan_coordinates_show_correct_page_without_external_ocr(tmp_path):
    path = tmp_path / "original.pdf"
    writer = PdfWriter()
    for _ in range(35):
        writer.add_blank_page(width=400, height=500)
    with path.open("wb") as output:
        writer.write(output)
    layout = {"checksum": hashlib.sha256(path.read_bytes()).hexdigest(), "pages": [{"page": 24, "width": 400, "height": 500, "words": [["Insurance", [10, 100, 90, 130]], ["commitments", [100, 100, 180, 130]], ["coverage", [190, 100, 250, 130]]]}]}
    (tmp_path / "visual-layout.json").write_text(json.dumps(layout), encoding="utf-8")
    with patch("app.services.document_visuals._ocr_words") as ocr:
        result = source_region(path, "application/pdf", "Show insurance commitments image", "Insurance commitments coverage")
    assert result["page"] == 24
    ocr.assert_not_called()


def test_saved_image_layout_is_used_when_ocr_disabled(tmp_path):
    path = tmp_path / "original.png"
    Image.new("RGB", (400, 500), "white").save(path)
    (tmp_path / "visual-layout.json").write_text(json.dumps({"checksum": hashlib.sha256(path.read_bytes()).hexdigest(), "pages": [{"page": 1, "width": 400, "height": 500, "words": [["Insurance", [10, 100, 90, 130]], ["commitments", [100, 100, 180, 130]], ["coverage", [190, 100, 250, 130]]]}]}), encoding="utf-8")
    with patch("app.services.document_visuals._ocr_words") as ocr:
        result = source_region(path, "image/png", "Show insurance commitments image", "Insurance commitments coverage")
    assert result["page"] == 1
    ocr.assert_not_called()


def test_google_vision_returns_layout_without_writing_files_during_extraction(tmp_path):
    source = tmp_path / "original.png"
    Image.new("RGB", (400, 500), "white").save(source)
    annotation = {"text": "Insurance commitments coverage", "pages": [{"width": 400, "height": 500, "blocks": [{"paragraphs": [{"words": [{"symbols": [{"text": "Insurance"}], "boundingBox": {"vertices": [{"x": 10, "y": 100}, {"x": 90, "y": 100}, {"x": 90, "y": 130}, {"x": 10, "y": 130}]}}]}]}]}]}
    with patch.object(cloud_ocr, "_json_request", return_value={"responses": [{"fullTextAnnotation": annotation}]}):
        text = cloud_ocr._google_vision(source, "image/png")
    assert text == "Insurance commitments coverage"
    assert text.visual_layout["pages"][0]["words"][0][0] == "Insurance"
    assert not (tmp_path / "visual-layout.json").exists()


def test_preview_checks_access_before_reading_file():
    db = MagicMock()
    with patch("app.api.routes.documents.require_document_access", side_effect=HTTPException(403, "Forbidden")), patch("app.api.routes.documents._document_source_path") as path:
        with pytest.raises(HTTPException) as error:
            get_source_region(uuid4(), SourceRegionRequest(chunk_id=uuid4(), query="show image"), Response(), db, SimpleNamespace())
    assert error.value.status_code == 403
    path.assert_not_called()


def test_missing_or_cross_document_chunk_does_not_read_source():
    db = MagicMock()
    db.scalar.return_value = None
    with patch("app.api.routes.documents.require_document_access", return_value=SimpleNamespace()), patch("app.api.routes.documents._document_source_path") as path:
        with pytest.raises(HTTPException) as error:
            get_source_region(uuid4(), SourceRegionRequest(chunk_id=uuid4(), query="show image"), Response(), db, SimpleNamespace())
    assert error.value.status_code == 404
    path.assert_not_called()
