"""Opt-in OCR providers for scanned documents.

MinerU uses its hosted asynchronous Precision API, so no local model is loaded.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from io import BytesIO
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile
from app.services.processing_cancellation import ProcessingCancelled, check_processing_cancelled

from app.core.config import (
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
    AZURE_DOCUMENT_INTELLIGENCE_KEY,
    GOOGLE_VISION_API_KEY,
    JINA_API_KEY,
    JINA_OCR_API_BASE_URL,
    JINA_OCR_MODEL,
    MINERU_API_BASE_URL,
    MINERU_API_TOKEN,
    MINERU_LANGUAGE,
    MINERU_MODEL_VERSION,
    MINERU_POLL_SECONDS,
    MINERU_TIMEOUT_SECONDS,
    OCR_LANGUAGE_HINTS,
    OCR_MAX_PAGES,
    OCR_PROVIDER,
    OCR_TIMEOUT_SECONDS,
)


class OCRUnavailableError(RuntimeError):
    """OCR was needed but no configured provider could return text."""


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRResult:
    text: str
    provenance: dict[str, str]
    visual_layout: dict | None = None


class OCRText(str):
    def __new__(cls, text: str, visual_layout: dict):
        result = super().__new__(cls, text)
        result.visual_layout = visual_layout
        return result


def extract_scanned_document_text(file_path: Path, content_type: str) -> str:
    return extract_scanned_document_text_with_provenance(file_path, content_type).text


def extract_scanned_document_text_with_provenance(file_path: Path, content_type: str) -> OCRResult:
    providers = _providers()
    if not providers:
        raise OCRUnavailableError(
            "This document has no embedded text. Configure OCR_PROVIDER with MinerU, Jina, Google Vision, or Azure Document Intelligence."
        )

    errors: list[str] = []
    for provider in providers:
        check_processing_cancelled()
        try:
            raw_text = provider(file_path, content_type)
            text = raw_text.strip()
            if text:
                provider_name = _provider_name(provider)
                model = {
                    "jina": JINA_OCR_MODEL,
                    "mineru": MINERU_MODEL_VERSION,
                }.get(provider_name)
                provenance = {"provider": provider_name, "completed_at": datetime.now(timezone.utc).isoformat()}
                if model:
                    provenance["model"] = model
                return OCRResult(text=text, provenance=provenance, visual_layout=raw_text.visual_layout if isinstance(raw_text, OCRText) else None)
            errors.append("provider returned no text")
            if provider is not providers[-1]:
                logger.warning(
                    "OCR provider returned no text; trying fallback",
                    extra={"provider": _provider_name(provider), "error_type": "EmptyResult"},
                )
        except OCRUnavailableError as exc:
            errors.append(str(exc))
            logger.warning("OCR provider request failed", extra={"provider": _provider_name(provider), "error_type": type(exc).__name__, "error_summary": str(exc)[:500]})
            if provider is not providers[-1]:
                logger.warning(
                    "OCR provider failed; trying fallback",
                    extra={"provider": _provider_name(provider), "error_type": type(exc).__name__},
                )
    raise OCRUnavailableError("OCR could not read this document. " + " | ".join(errors[:2]))


def _provider_name(provider) -> str:
    return next(
        name
        for name, candidate in (
            ("jina", _jina),
            ("mineru", _mineru),
            ("google_vision", _google_vision),
            ("azure_document_intelligence", _azure_document_intelligence),
        )
        if provider is candidate
    )


def _providers():
    if OCR_PROVIDER == "disabled":
        return []
    available = []
    if MINERU_API_TOKEN:
        available.append(_mineru)
    if GOOGLE_VISION_API_KEY:
        available.append(_google_vision)
    if AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY:
        available.append(_azure_document_intelligence)
    if OCR_PROVIDER == "jina":
        # Jina is primary by explicit configuration; MinerU is a fallback for
        # missing credentials, provider errors, timeouts, or empty OCR output.
        return ([_jina] if JINA_API_KEY else []) + ([_mineru] if MINERU_API_TOKEN else [])
    if OCR_PROVIDER == "google_vision":
        return [_google_vision] if GOOGLE_VISION_API_KEY else []
    if OCR_PROVIDER == "azure_document_intelligence":
        return [_azure_document_intelligence] if AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY else []
    if OCR_PROVIDER == "mineru":
        return [_mineru] if MINERU_API_TOKEN else []
    return available


def _jina(file_path: Path, content_type: str) -> str:
    """Send one document to Jina's hosted OCR model and return Markdown.

    This is deliberately an explicit provider rather than part of ``auto``.
    The file content leaves Nexora, so operators must enable it only for
    approved, non-sensitive evaluation documents.
    """
    if not JINA_API_KEY:
        raise OCRUnavailableError("Jina OCR requires JINA_API_KEY")
    pages = _vision_pages(file_path, content_type)
    page_content_type = "image/png" if content_type == "application/pdf" else content_type
    page_texts = []
    for page in pages:
        check_processing_cancelled()
        page_texts.append(_jina_page(page, page_content_type))
    return "\n\n".join(text for text in page_texts if text)


def _jina_page(page: bytes, content_type: str) -> str:
    encoded = base64.b64encode(page).decode("ascii")
    payload = {
        "model": JINA_OCR_MODEL,
        "stream": False,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Transcribe the provided document page into clean Markdown, preserving the natural reading order. Do not answer questions or infer missing content.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                },
            ],
        }],
    }
    request = Request(
        f"{JINA_OCR_API_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {JINA_API_KEY}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=OCR_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Never persist the response body, URL or API key.
        raise OCRUnavailableError(f"Jina OCR request failed (HTTP {exc.code})") from exc
    except TimeoutError as exc:
        raise OCRUnavailableError("Jina OCR request timed out") from exc
    except URLError as exc:
        reason = "timed out" if isinstance(exc.reason, TimeoutError) else "network error"
        raise OCRUnavailableError(f"Jina OCR request failed: {reason}") from exc
    except OSError as exc:
        raise OCRUnavailableError("Jina OCR request failed: network error") from exc
    except json.JSONDecodeError as exc:
        raise OCRUnavailableError("Jina OCR returned an invalid JSON response") from exc
    choices = result.get("choices") or []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else None
    text = message.get("content") if isinstance(message, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise OCRUnavailableError("Jina OCR returned no document text")
    return text.strip()


def _mineru(file_path: Path, content_type: str) -> str:
    """Upload one document to MinerU and return its generated Markdown."""
    if not MINERU_API_TOKEN:
        raise OCRUnavailableError("MinerU OCR requires MINERU_API_TOKEN")
    data_id = hashlib.sha256(file_path.read_bytes()).hexdigest()
    headers = {"Authorization": f"Bearer {MINERU_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "files": [{"name": file_path.name, "data_id": data_id, "is_ocr": True}],
        "model_version": MINERU_MODEL_VERSION,
        "language": MINERU_LANGUAGE,
        "enable_formula": False,
        "enable_table": True,
    }
    submitted = _mineru_json_request(f"{MINERU_API_BASE_URL}/file-urls/batch", headers=headers, payload=payload)
    batch_id, upload_url = _mineru_upload_target(submitted)
    _mineru_upload(upload_url, file_path.read_bytes())
    result = _mineru_wait_for_result(batch_id, headers)
    return _mineru_markdown(result)


def _mineru_upload_target(response: dict) -> tuple[str, str]:
    data = _mineru_success_data(response)
    batch_id = data.get("batch_id")
    urls = data.get("file_urls") or []
    if not isinstance(batch_id, str) or not batch_id or not urls or not isinstance(urls[0], str):
        raise OCRUnavailableError("MinerU did not return an upload target")
    return batch_id, urls[0]


def _mineru_upload(upload_url: str, content: bytes) -> None:
    """PUT raw bytes without a Content-Type header to MinerU's signed URL.

    urllib adds ``application/x-www-form-urlencoded`` for request bodies. That
    extra header invalidates the object-storage signature issued by MinerU.
    """
    check_processing_cancelled()
    target = urlsplit(upload_url)
    if target.scheme not in {"http", "https"} or not target.netloc:
        raise OCRUnavailableError("MinerU returned an invalid upload URL")
    connection_type = HTTPSConnection if target.scheme == "https" else HTTPConnection
    connection = None
    try:
        # A failed external upload must not hold the single document worker for
        # the full asynchronous OCR job window. Transient transport failures
        # are retried by the job queue with backoff.
        connection = connection_type(target.netloc, timeout=OCR_TIMEOUT_SECONDS)
        request_target = target.path or "/"
        if target.query:
            request_target = f"{request_target}?{target.query}"
        connection.request("PUT", request_target, body=content, headers={"Content-Length": str(len(content))})
        response = connection.getresponse()
        response.read()
        if 200 <= response.status < 300:
            return
        raise OCRUnavailableError(f"MinerU file upload failed (HTTP {response.status})")
    except (HTTPException, OSError, TimeoutError) as exc:
        # Do not include the signed URL: it can grant temporary access to the
        # object. The transport reason is sufficient for an operator to act.
        raise OCRUnavailableError(f"MinerU file upload failed: network error ({exc})") from exc
    finally:
        if connection is not None:
            connection.close()


def _mineru_wait_for_result(batch_id: str, headers: dict[str, str]) -> dict:
    deadline = time.monotonic() + MINERU_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        check_processing_cancelled()
        response = _mineru_json_request(f"{MINERU_API_BASE_URL}/extract-results/batch/{batch_id}", headers=headers)
        data = _mineru_success_data(response)
        results = data.get("extract_result") or []
        result = results[0] if results else {}
        state = result.get("state")
        if state == "done":
            return result
        if state == "failed":
            raise OCRUnavailableError(f"MinerU could not read this document: {result.get('err_msg') or 'unknown error'}")
        time.sleep(MINERU_POLL_SECONDS)
    raise OCRUnavailableError("MinerU OCR timed out")


def _mineru_success_data(response: dict) -> dict:
    if response.get("code") != 0 or not isinstance(response.get("data"), dict):
        raise OCRUnavailableError(f"MinerU request failed: {response.get('msg') or 'unknown error'}")
    return response["data"]


def _mineru_json_request(url: str, *, headers: dict[str, str], payload: dict | None = None) -> dict:
    check_processing_cancelled()
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=OCR_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OCRUnavailableError("MinerU request failed") from exc


def _mineru_markdown(result: dict) -> str:
    zip_url = result.get("full_zip_url")
    if not isinstance(zip_url, str) or not zip_url:
        raise OCRUnavailableError("MinerU did not return an extraction archive")
    try:
        with urlopen(zip_url, timeout=OCR_TIMEOUT_SECONDS) as response:
            archive = response.read()
        with ZipFile(BytesIO(archive)) as bundle:
            markdown_names = [name for name in bundle.namelist() if name.endswith("/full.md") or name == "full.md"]
            if len(markdown_names) != 1:
                raise OCRUnavailableError("MinerU archive did not contain one Markdown result")
            return bundle.read(markdown_names[0]).decode("utf-8").strip()
    except OCRUnavailableError:
        raise
    except (HTTPError, URLError, TimeoutError, BadZipFile, UnicodeDecodeError) as exc:
        raise OCRUnavailableError("MinerU result archive could not be read") from exc


def _google_vision(file_path: Path, content_type: str) -> str:
    from app.services.document_visuals import annotation_words
    pages = _vision_pages(file_path, content_type)
    chunks: list[str] = []
    layout_pages = []
    for page_number, page in enumerate(pages, 1):
        check_processing_cancelled()
        payload = {
            "requests": [{
                "image": {"content": base64.b64encode(page).decode("ascii")},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "imageContext": {"languageHints": OCR_LANGUAGE_HINTS},
            }]
        }
        response = _json_request(
            f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}",
            payload,
        )
        item = (response.get("responses") or [{}])[0]
        if item.get("error"):
            raise OCRUnavailableError(f"Google Vision: {item['error'].get('message', 'request failed')}")
        text = (item.get("fullTextAnnotation") or {}).get("text", "").strip()
        annotation = item.get("fullTextAnnotation") or {}
        dimensions = (annotation.get("pages") or [{}])[0]
        if dimensions.get("width") and dimensions.get("height"):
            layout_pages.append({"page": page_number, "width": dimensions["width"], "height": dimensions["height"], "words": annotation_words(annotation)})
        if text:
            chunks.append(text)
    if layout_pages:
        check_processing_cancelled()
        with file_path.open("rb") as source:
            checksum = hashlib.file_digest(source, "sha256").hexdigest()
        return OCRText("\n\n".join(chunks), {"checksum": checksum, "pages": layout_pages})
    return "\n\n".join(chunks)


def _vision_pages(file_path: Path, content_type: str) -> list[bytes]:
    if content_type != "application/pdf":
        return [file_path.read_bytes()]
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise OCRUnavailableError("PDF OCR requires the pypdfium2 package") from exc
    try:
        pdf = pdfium.PdfDocument(str(file_path))
        if len(pdf) > OCR_MAX_PAGES:
            raise OCRUnavailableError(f"PDF OCR is limited to {OCR_MAX_PAGES} pages")
        pages: list[bytes] = []
        for index in range(len(pdf)):
            check_processing_cancelled()
            image = pdf[index].render(scale=2).to_pil()
            from io import BytesIO
            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            pages.append(buffer.getvalue())
        return pages
    except (OCRUnavailableError, ProcessingCancelled):
        raise
    except Exception as exc:
        raise OCRUnavailableError("Could not render the PDF for OCR") from exc


def _azure_document_intelligence(file_path: Path, content_type: str) -> str:
    request = Request(
        f"{AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30",
        data=file_path.read_bytes(),
        headers={"Ocp-Apim-Subscription-Key": AZURE_DOCUMENT_INTELLIGENCE_KEY, "Content-Type": content_type},
        method="POST",
    )
    try:
        with urlopen(request, timeout=OCR_TIMEOUT_SECONDS) as response:
            operation_url = response.headers.get("Operation-Location")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise OCRUnavailableError("Azure Document Intelligence request failed") from exc
    if not operation_url:
        raise OCRUnavailableError("Azure Document Intelligence did not return an operation URL")
    deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        check_processing_cancelled()
        poll = Request(operation_url, headers={"Ocp-Apim-Subscription-Key": AZURE_DOCUMENT_INTELLIGENCE_KEY})
        try:
            with urlopen(poll, timeout=min(10, OCR_TIMEOUT_SECONDS)) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OCRUnavailableError("Azure Document Intelligence result could not be read") from exc
        if result.get("status") == "succeeded":
            return (result.get("analyzeResult") or {}).get("content", "")
        if result.get("status") == "failed":
            raise OCRUnavailableError("Azure Document Intelligence could not read this document")
        time.sleep(0.5)
    raise OCRUnavailableError("Azure Document Intelligence timed out")


def _json_request(url: str, payload: dict) -> dict:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=OCR_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OCRUnavailableError("Google Vision request failed") from exc
