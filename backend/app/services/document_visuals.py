"""Locate and render real source regions. Never synthesize a document image."""
import base64
import io
import json
import hashlib
import re
import unicodedata
from pathlib import Path
from contextlib import closing

import pypdfium2 as pdfium
from PIL import Image

from app.core.config import GOOGLE_VISION_API_KEY, OCR_PROVIDER


class VisualUnavailable(ValueError):
    pass


_STOP = set("عکس تصویر تصاویر اسکرین شات نشان بده نمایش بخش قسمت فایل سند جدول از را رو و در به این آن لطفا لطفاً میخواهم میخوام می خواهم می‌خواهم می‌خوام بفرست ببینم ارسال کن show send display give want need image picture screenshot photo of the a an in document file table please me".split())


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().translate(str.maketrans("يك", "یک"))


def terms(text: str) -> set[str]:
    return {word for word in re.findall(r"\w+", normalize(text)) if len(word) > 1 and word not in _STOP}


def wants_document_image(question: str) -> bool:
    return bool(re.search(r"عکس|تصویر|اسکرین\s*شات|\b(image|picture|screenshot|photo)\b", question, re.I) and re.search(r"نشان|نمایش|بفرست|بده|می.?خواهم|می.?خوام|\b(show|send|display|give|want|need)\b", question, re.I))


def _locate(words: list[tuple[str, tuple[float, float, float, float]]], query: str, excerpt: str):
    """Require query matches and source evidence in a nearby region, not just anywhere on a page."""
    requested = terms(query)
    evidence = terms(excerpt)
    best = None
    for start in range(0, len(words), 8):
        window = words[max(0, start - 8):start + 64]
        tokens = set().union(*(terms(word) for word, _ in window)) if window else set()
        hits = requested & tokens
        support = evidence & tokens
        if not requested or len(hits) < min(2, len(requested)) or len(support) < min(3, len(evidence)) or not support:
            continue
        score = len(hits) / len(requested) + min(len(support), 20) / 100
        if best is None or score > best[0]:
            matched = [box for word, box in window if terms(word) & (hits | support)]
            best = (score, (min(b[0] for b in matched), min(b[1] for b in matched), max(b[2] for b in matched), max(b[3] for b in matched)))
    return best


def _native_words(page):
    width, height = page.get_size()
    rotation = page.get_rotation()
    words = []
    with closing(page.get_textpage()) as text:
        count = text.count_chars()
        if count > 20_000:
            raise VisualUnavailable("Source page is too complex for a safe region preview")
        # Read characters individually: PDFium text indices can differ from char indices.
        word = ""
        boxes = []
        for index in range(count):
            char = text.get_text_range(index, 1)
            if not char or char.isspace():
                if word and boxes:
                    words.append((word, (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))))
                word, boxes = "", []
                continue
            left, bottom, right, top = text.get_charbox(index)
            word += char
            if rotation == 90:
                boxes.append((bottom, left, top, right))
            elif rotation == 180:
                boxes.append((width - right, bottom, width - left, top))
            elif rotation == 270:
                boxes.append((width - top, height - right, width - bottom, height - left))
            else:
                boxes.append((left, height - top, right, height - bottom))
        if word and boxes:
            words.append((word, (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))))
    return words


def _render(page):
    width, height = page.get_size()
    if width <= 0 or height <= 0:
        raise VisualUnavailable("Invalid source page dimensions")
    scale = min(2, 1800 / max(width, height))
    with closing(page.render(scale=scale)) as bitmap:
        return bitmap.to_pil().convert("RGB"), scale


def annotation_words(annotation):
    words = []
    for page in annotation.get("pages", []):
        for block in page.get("blocks", []):
            for paragraph in block.get("paragraphs", []):
                for word in paragraph.get("words", []):
                    vertices = word.get("boundingBox", {}).get("vertices", [])
                    if len(vertices) != 4:
                        continue
                    value = "".join(symbol.get("text", "") for symbol in word.get("symbols", []))
                    words.append((value, (min(v.get("x", 0) for v in vertices), min(v.get("y", 0) for v in vertices), max(v.get("x", 0) for v in vertices), max(v.get("y", 0) for v in vertices))))
    return words


def _ocr_words(image):
    # Reuse only an explicitly enabled coordinate-capable OCR provider.
    # Never send a private document to an unconfigured service.
    if OCR_PROVIDER != "google_vision" or not GOOGLE_VISION_API_KEY:
        raise VisualUnavailable("This scanned document needs coordinate-aware OCR (Google Vision) to locate a source region. No image was guessed.")
    from app.services.cloud_ocr import _json_request, OCRUnavailableError
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    try:
        response = _json_request(f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}", {
            "requests": [{"image": {"content": base64.b64encode(buffer.getvalue()).decode("ascii")}, "features": [{"type": "DOCUMENT_TEXT_DETECTION"}], "imageContext": {"languageHints": ["fa", "en"]}}]
        })
    except OCRUnavailableError as exc:
        raise VisualUnavailable("Coordinate-aware OCR is unavailable. Please retry later.") from exc
    item = (response.get("responses") or [{}])[0]
    if item.get("error"):
        raise VisualUnavailable("Coordinate-aware OCR could not read the source page")
    return annotation_words(item.get("fullTextAnnotation") or {})


def _saved_layout(path):
    sidecar = path.parent / "visual-layout.json"
    if not sidecar.is_file() or sidecar.stat().st_size > 20_000_000:
        return None
    try:
        layout = json.loads(sidecar.read_text(encoding="utf-8"))
        with path.open("rb") as source:
            checksum = hashlib.file_digest(source, "sha256").hexdigest()
        return layout if layout.get("checksum") == checksum else None
    except (OSError, ValueError, AttributeError):
        return None


def _crop(image, bounds):
    # Context margin prevents clipping glyphs. This is a source passage, not a claim
    # that a whole table or diagram has been segmented.
    left, top, right, bottom = bounds
    # Expand a passage to the surrounding ruled table only when real grid lines
    # connect across it. Do not guess the extent of borderless tables.
    gray = image.convert("L")
    pixels = gray.load()
    lines = []
    for y in range(image.height):
        start = None
        for x in range(image.width):
            dark = pixels[x, y] < 100
            if dark and start is None:
                start = x
            if start is not None and (not dark or x == image.width - 1):
                end = x if dark else x - 1
                if end - start >= image.width * .2:
                    if not lines or y - lines[-1][0] > 3:
                        lines.append((y, start, end))
                start = None
    groups = []
    for line in lines:
        if groups and line[0] - groups[-1][-1][0] < 140 and abs(line[1] - groups[-1][-1][1]) < 12 and abs(line[2] - groups[-1][-1][2]) < 12:
            groups[-1].append(line)
        else:
            groups.append([line])
    for group in groups:
        y1, x1, x2 = group[0]
        y2 = group[-1][0]
        connected = y2 > y1 and any(sum(pixels[x, y] < 100 for y in range(y1, y2 + 1)) > (y2 - y1) * .8 for x in [x1, x2])
        if len(group) >= 3 and connected and x1 <= (left + right) / 2 <= x2 and y1 <= (top + bottom) / 2 <= y2:
            left, top, right, bottom = min(left, x1), min(top, y1), max(right, x2), max(bottom, y2)
            break
    margin = 32
    box = (max(0, int(left - margin)), max(0, int(top - margin)), min(image.width, int(right + margin)), min(image.height, int(bottom + margin)))
    if box[2] <= box[0] or box[3] <= box[1]:
        raise VisualUnavailable("Source region is empty")
    crop = image.crop(box)
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG", optimize=True)
    return {"image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"), "bounds": list(box), "width": crop.width, "height": crop.height}


def source_region(path: Path, content_type: str, query: str, excerpt: str) -> dict:
    if content_type == "application/pdf":
        with pdfium.PdfDocument(str(path)) as pdf:
            if len(pdf) > 100:
                raise VisualUnavailable("Source region search supports PDFs of up to 100 pages")
            best = None
            layout = _saved_layout(path)
            if layout:
                for item in layout.get("pages", []):
                    match = _locate(item.get("words", []), query, excerpt)
                    index = item.get("page", 0) - 1
                    if match and 0 <= index < len(pdf) and (best is None or match[0] > best[0]):
                        best = (match[0], index, match[1], item["width"], item["height"])
                if best:
                    with closing(pdf[best[1]]) as page:
                        image, _ = _render(page)
                        bounds = [best[2][0] * image.width / best[3], best[2][1] * image.height / best[4], best[2][2] * image.width / best[3], best[2][3] * image.height / best[4]]
                        return {"page": best[1] + 1, **_crop(image, bounds)}
            scanned = []
            for index in range(len(pdf)):
                with closing(pdf[index]) as page:
                    words = _native_words(page)
                    if not words:
                        scanned.append(index)
                    match = _locate(words, query, excerpt)
                    if match and (best is None or match[0] > best[0]):
                        best = (match[0], index, match[1])
            if best:
                with closing(pdf[best[1]]) as page:
                    image, scale = _render(page)
                    return {"page": best[1] + 1, **_crop(image, [value * scale for value in best[2]])}
            if scanned:
                # Bound remote OCR work per preview; do not silently scan a large file.
                if len(scanned) > 1:
                    raise VisualUnavailable("This scanned PDF needs page-level OCR coordinates before a region can be shown. Reprocess it with coordinate-aware OCR.")
                # Larger scans must be reprocessed so page-level layout is retained.
                for index in scanned[:1]:
                    with closing(pdf[index]) as page:
                        image, _ = _render(page)
                        match = _locate(_ocr_words(image), query, excerpt)
                        if match:
                            return {"page": index + 1, **_crop(image, match[1])}
    elif content_type in {"image/png", "image/jpeg", "image/tiff"}:
        with Image.open(path) as original:
            original.seek(0)
            image = original.convert("RGB")
            image.thumbnail((1800, 1800))
            layout = _saved_layout(path)
            item = next(iter(layout.get("pages", [])), None) if layout else None
            match = _locate(item["words"] if item else _ocr_words(image), query, excerpt)
            if match:
                bounds = match[1]
                if item:
                    bounds = [bounds[0] * image.width / item["width"], bounds[1] * image.height / item["height"], bounds[2] * image.width / item["width"], bounds[3] * image.height / item["height"]]
                return {"page": 1, **_crop(image, bounds)}
    else:
        raise VisualUnavailable("Source images are supported for PDF, PNG, JPG and TIFF documents")
    raise VisualUnavailable("The requested region could not be confidently located in the original document")
