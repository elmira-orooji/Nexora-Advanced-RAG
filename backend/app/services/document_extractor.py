import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.services.cloud_ocr import OCRUnavailableError, extract_scanned_document_text_with_provenance
from app.services.processing_cancellation import ProcessingCancelled, check_processing_cancelled


class ExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    ocr_provenance: dict[str, str] | None = None


# Supported MIME types mapped to extraction functions
_EXTRACTORS: dict[str, str] = {
    "application/pdf": "_extract_pdf",
    "image/jpeg": "_extract_image",
    "image/png": "_extract_image",
    "image/tiff": "_extract_image",
    "text/plain": "_extract_text_file",
    "text/markdown": "_extract_text_file",
    "text/csv": "_extract_csv",
    "application/json": "_extract_json",
}


def supported_content_types() -> list[str]:
    """Return the list of MIME types this extractor can handle."""
    return sorted(_EXTRACTORS.keys())


def extract_text(file_path: Path, content_type: str) -> str:
    return extract_text_with_provenance(file_path, content_type).text


def extract_text_with_provenance(file_path: Path, content_type: str) -> ExtractionResult:
    handler_name = _EXTRACTORS.get(content_type)
    if handler_name is None:
        raise ExtractionError(
            f"Unsupported file type '{content_type}'. "
            f"Supported types: {', '.join(supported_content_types())}"
        )
    if handler_name == "_extract_pdf":
        return _extract_pdf_with_provenance(file_path)
    if handler_name == "_extract_image":
        return _extract_image_with_provenance(file_path)
    handler = globals()[handler_name]
    return ExtractionResult(text=handler(file_path))


def _extract_pdf(file_path: Path) -> str:
    return _extract_pdf_with_provenance(file_path).text


def _extract_pdf_with_provenance(file_path: Path) -> ExtractionResult:
    try:
        reader = PdfReader(file_path)
        parts = []
        for page in reader.pages:
            check_processing_cancelled()
            parts.append((page.extract_text() or "").strip())
        text = "\n\n".join(parts)
    except ProcessingCancelled:
        raise
    except Exception as exc:
        raise ExtractionError("Could not read the PDF file") from exc

    text = text.strip()
    if text:
        return ExtractionResult(text=text)
    try:
        result = extract_scanned_document_text_with_provenance(file_path, "application/pdf")
        return ExtractionResult(text=result.text, ocr_provenance=result.provenance)
    except OCRUnavailableError as exc:
        raise ExtractionError(str(exc)) from exc


def _extract_image(file_path: Path) -> str:
    return _extract_image_with_provenance(file_path).text


def _extract_image_with_provenance(file_path: Path) -> ExtractionResult:
    try:
        result = extract_scanned_document_text_with_provenance(file_path, _content_type_for_image(file_path))
    except OCRUnavailableError as exc:
        raise ExtractionError(str(exc)) from exc
    if not result.text.strip():
        raise ExtractionError("No text was found in the image")
    return ExtractionResult(text=result.text, ocr_provenance=result.provenance)


def _content_type_for_image(file_path: Path) -> str:
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".tif": "image/tiff", ".tiff": "image/tiff"}.get(file_path.suffix.lower(), "image/png")


def _extract_text_file(file_path: Path) -> str:
    try:
        text = file_path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ExtractionError("Text files must use UTF-8 encoding") from exc

    if not text:
        raise ExtractionError("The text file is empty")
    return text


def _extract_csv(file_path: Path) -> str:
    """Extract CSV content as readable text with headers preserved."""
    try:
        raw = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError("CSV files must use UTF-8 encoding") from exc

    if not raw.strip():
        raise ExtractionError("The CSV file is empty")

    try:
        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)
    except csv.Error as exc:
        raise ExtractionError("Could not parse the CSV file") from exc

    if not rows:
        raise ExtractionError("The CSV file contains no data")

    # Convert to readable text: header row as labels, then each row as key-value pairs
    lines: list[str] = []
    headers = rows[0]
    for row_index, row in enumerate(rows[1:], start=1):
        parts = []
        for header, value in zip(headers, row):
            value = value.strip()
            if value:
                parts.append(f"{header}: {value}")
        if parts:
            lines.append(f"Row {row_index}: " + "; ".join(parts))

    text = "\n".join(lines).strip()
    if not text:
        raise ExtractionError("The CSV file contains no meaningful data")
    return text


def _extract_json(file_path: Path) -> str:
    """Extract JSON content as formatted, human-readable text."""
    import json

    try:
        raw = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError("JSON files must use UTF-8 encoding") from exc

    if not raw.strip():
        raise ExtractionError("The JSON file is empty")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExtractionError("Could not parse the JSON file") from exc

    # Pretty-print for LLM consumption; truncate extremely large payloads
    text = json.dumps(data, indent=2, ensure_ascii=False)
    max_chars = 500_000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text
