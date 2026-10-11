"""Update the formatted SRS without rebuilding its university template."""
from copy import deepcopy
from pathlib import Path
import argparse
import ast
import re
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
args = parser.parse_args()
doc = Document(args.source)
output = root / "documents/requirements/Nexora-SRS.docx"

# Reuse the current evidence list rather than maintaining a second path map.
tree = ast.parse((root / "documents/scripts/build_srs_expanded.py").read_text(encoding="utf-8-sig"))
sources = next(ast.literal_eval(node.value) for node in tree.body
               if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "sources" for t in node.targets))
source_map = dict(sources)

def replace_text(paragraph, before, after):
    """Replace across split XML runs while retaining surrounding formatting."""
    nodes = list(paragraph._p.iter(qn("w:t")))
    text = "".join(node.text or "" for node in nodes)
    start = text.find(before)
    if start < 0:
        return False
    end = start + len(before)
    offset = 0
    inserted = False
    for node in nodes:
        value = node.text or ""
        node_end = offset + len(value)
        if node_end > start and offset < end:
            prefix = value[:max(0, start - offset)]
            suffix = value[max(0, end - offset):] if node_end > end else ""
            node.text = prefix + (after if not inserted else "") + suffix
            node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            inserted = True
        offset = node_end
    return True

paragraphs = [Paragraph(element, doc._body) for element in doc.element.body.iter(qn("w:p"))]
for paragraph in paragraphs:
    match = re.match(r"^•\s*(C\d{2})\s*[—-]", paragraph.text)
    if match and match.group(1) in source_map:
        replace_text(paragraph, paragraph.text, f"•  {match.group(1)} — {source_map[match.group(1)]}")
    replace_text(paragraph, "frontend/my-rag-app", "frontend/app")
    replace_text(paragraph, "موفقیت کپی باید فقط پس از موفقیت Clipboard گزارش شود.",
                 "موفقیت کپی باید فقط پس از موفقیت Clipboard، به‌صورت پیام کوتاه زیر آیکون کپی نمایش داده شود؛ پیام موفقیت سراسری نمایش داده نشود.")
    replace_text(paragraph, "کاربر باید نظر مثبت یا منفی را به پاسخ مشخص ثبت کند و نتیجه واقعی ثبت را ببیند.",
                 "کاربر باید نظر مثبت یا منفی را به پاسخ مشخص ثبت کند و نتیجه واقعی ثبت را به‌صورت پیام کوتاه کنار کنترل بازخورد ببیند؛ پیام موفقیت سراسری نمایش داده نشود.")

anchor = next(p for p in paragraphs if p.text.startswith("رابط کاربری با React و Vite ساخته شده"))
replace_text(anchor, anchor.text,
             "رابط کاربری با React و Vite ساخته شده و با API مبتنی بر FastAPI ارتباط دارد. PostgreSQL داده‌های عملیاتی و Qdrant بردارهای بازیابی را نگه می‌دارند؛ فایل اصلی سند در فضای ذخیره‌سازی اسناد قرار می‌گیرد. در محیط توسعه، رابط معمولاً روی پورت ۵۱۷۳ و API روی پورت ۸۰۰۰ اجرا می‌شود. این پورت‌ها الزام استقرار تولید نیستند.")

notes = [
    "بازبینی فنی این نسخه در ۱۹ مهر ۱۴۰۵ انجام شده است. مسیر رابط به frontend/app تغییر کرده و بخش‌های تخصصی آن در src/features دسته‌بندی شده‌اند. سرویس‌های بک‌اند در backend/app/services بر اساس پردازش اسناد، بازیابی، ارائه‌دهندگان، اتصال‌ها، عملیات، امنیت، ذخیره‌سازی و جریان‌های کاربردی تفکیک شده‌اند. این بازآرایی، قراردادهای API و شناسه‌های نیازمندی را تغییر نمی‌دهد.",
    "برای اجرای محلی، در یک ترمینال از backend محیط مجازی را فعال کنید و uvicorn app.main:app --host 0.0.0.0 --port 8000 را اجرا کنید. در ترمینال دیگر، از frontend/app دستور npm run dev -- --host 0.0.0.0 --port 5173 --strictPort را اجرا کنید. Worker اسناد با python -m app.workers.document_worker و زمان‌بند اتصال‌ها با python -m app.workers.connector_scheduler_worker در فرایندهای جداگانه اجرا می‌شوند.",
    "وضعیت بارگذاری هر فایل در صف آپلود نمایش داده می‌شود و پایان انتقال به معنی پایان پردازش نیست. برای بارگذاری فایل، ذخیره مجموعه و حذف گفتگو، پیام موفقیت سراسری نمایش داده نمی‌شود. پیام‌های موفقیت کپی و ثبت بازخورد، کوتاه و کنار همان کنترل هستند؛ خطاهای عملیات همچنان باید نمایش داده شوند.",
]
for note in notes:
    element = deepcopy(anchor._p)
    new = Paragraph(element, doc._body)
    for child in list(element):
        if child.tag != qn("w:pPr"):
            element.remove(child)
    run = new.add_run(note)
    if anchor.runs and anchor.runs[0]._r.rPr is not None:
        run._r.insert(0, deepcopy(anchor.runs[0]._r.rPr))
    anchor._p.addnext(element)
    anchor = new

all_text = "\n".join(p.text for p in paragraphs)
assert "frontend/my-rag-app" not in all_text
assert all(code in all_text for code in source_map)
doc.core_properties.comments = "Technical paths and operation feedback updated on 2026-10-11."
doc.save(output)
print(output)
