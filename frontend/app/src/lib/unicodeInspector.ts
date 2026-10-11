export type UnicodeFindingKind = "arabic-variant" | "bidi-control" | "invisible-format" | "replacement";

export interface UnicodeFinding {
  character: string;
  codePoint: string;
  labelFa: string;
  labelEn: string;
  detailFa: string;
  detailEn: string;
  kind: UnicodeFindingKind;
  count: number;
}
export interface UnicodeInspection {
  codePointCount: number;
  utf16UnitCount: number;
  findings: UnicodeFinding[];
}

const CHARACTER_DETAILS: Record<number, Omit<UnicodeFinding, "character" | "codePoint" | "count">> = {
  0x0649: { kind: "arabic-variant", labelFa: "الف مقصورهٔ عربی", labelEn: "Arabic alef maksura", detailFa: "ممکن است در متن فارسی با «ی» اشتباه شود؛ تبدیل خودکار انجام نمی‌شود.", detailEn: "Can be confused with Persian yeh; no automatic conversion is applied." },
  0x064a: { kind: "arabic-variant", labelFa: "یای عربی", labelEn: "Arabic yeh", detailFa: "با «ی» فارسی (U+06CC) متفاوت است و ممکن است جست‌وجوی دقیق را تحت‌تأثیر بگذارد.", detailEn: "Differs from Persian yeh (U+06CC) and may affect exact text matching." },
  0x0643: { kind: "arabic-variant", labelFa: "کاف عربی", labelEn: "Arabic kaf", detailFa: "با «ک» فارسی (U+06A9) متفاوت است و ممکن است جست‌وجوی دقیق را تحت‌تأثیر بگذارد.", detailEn: "Differs from Persian kaf (U+06A9) and may affect exact text matching." },
  0x0629: { kind: "arabic-variant", labelFa: "تای مربوطة", labelEn: "Arabic teh marbuta", detailFa: "این نویسه از نظر یونیکد با «ه» فارسی یکی نیست؛ تبدیل آن به بافت متن بستگی دارد.", detailEn: "This is not the same Unicode character as Persian heh; conversion depends on context." },
  0x06c0: { kind: "arabic-variant", labelFa: "هاء با یای بالا", labelEn: "Heh with yeh above", detailFa: "نویسه‌ای عربی است که گاهی با شکل‌های فارسی اشتباه گرفته می‌شود.", detailEn: "An Arabic character that may be confused with Persian forms." },
  0x061c: { kind: "bidi-control", labelFa: "نشانگر جهت عربی (ALM)", labelEn: "Arabic letter mark (ALM)", detailFa: "روی ترتیب نمایش متن دوجهته اثر می‌گذارد؛ ممکن است عمدی باشد.", detailEn: "Affects bidirectional display order and may be intentional." },
  0x200e: { kind: "bidi-control", labelFa: "نشانگر چپ‌به‌راست (LRM)", labelEn: "Left-to-right mark (LRM)", detailFa: "کنترل نامرئی جهت متن است؛ ممکن است برای ترکیب فارسی و لاتین لازم باشد.", detailEn: "An invisible direction control; it may be needed in mixed Persian and Latin text." },
  0x200f: { kind: "bidi-control", labelFa: "نشانگر راست‌به‌چپ (RLM)", labelEn: "Right-to-left mark (RLM)", detailFa: "کنترل نامرئی جهت متن است؛ ممکن است عمدی باشد.", detailEn: "An invisible direction control and may be intentional." },
  0x202a: { kind: "bidi-control", labelFa: "آغاز تعبیهٔ چپ‌به‌راست (LRE)", labelEn: "Left-to-right embedding (LRE)", detailFa: "روی ترتیب نمایش اثر می‌گذارد؛ حذف یا بازنویسی خودکار نمی‌شود.", detailEn: "Affects display order; it is not removed or rewritten automatically." },
  0x202b: { kind: "bidi-control", labelFa: "آغاز تعبیهٔ راست‌به‌چپ (RLE)", labelEn: "Right-to-left embedding (RLE)", detailFa: "روی ترتیب نمایش اثر می‌گذارد؛ حذف یا بازنویسی خودکار نمی‌شود.", detailEn: "Affects display order; it is not removed or rewritten automatically." },
  0x202c: { kind: "bidi-control", labelFa: "پایان تعبیهٔ جهت (PDF)", labelEn: "Pop directional formatting (PDF)", detailFa: "بازهٔ قالب‌بندی جهت‌دار را می‌بندد و ممکن است عمدی باشد.", detailEn: "Closes a directional formatting span and may be intentional." },
  0x202d: { kind: "bidi-control", labelFa: "تغییر جهت اجباری چپ‌به‌راست (LRO)", labelEn: "Left-to-right override (LRO)", detailFa: "روی ترتیب نمایش اثر می‌گذارد؛ متن را تغییر ندهید مگر دلیل مشخصی داشته باشید.", detailEn: "Affects display order; do not alter without a clear reason." },
  0x202e: { kind: "bidi-control", labelFa: "تغییر جهت اجباری راست‌به‌چپ (RLO)", labelEn: "Right-to-left override (RLO)", detailFa: "می‌تواند ترتیب نمایشی متن را عوض کند؛ برای بررسی امنیتی به آن توجه کنید.", detailEn: "Can reorder displayed text; review it as a potential security concern." },
  0x2066: { kind: "bidi-control", labelFa: "آغاز جداساز چپ‌به‌راست (LRI)", labelEn: "Left-to-right isolate (LRI)", detailFa: "جهت بخش داخلی را از متن پیرامون جدا می‌کند و ممکن است عمدی باشد.", detailEn: "Isolates an embedded direction from surrounding text and may be intentional." },
  0x2067: { kind: "bidi-control", labelFa: "آغاز جداساز راست‌به‌چپ (RLI)", labelEn: "Right-to-left isolate (RLI)", detailFa: "جهت بخش داخلی را از متن پیرامون جدا می‌کند و ممکن است عمدی باشد.", detailEn: "Isolates an embedded direction from surrounding text and may be intentional." },
  0x2068: { kind: "bidi-control", labelFa: "آغاز جداساز با جهت خودکار (FSI)", labelEn: "First strong isolate (FSI)", detailFa: "جهت بخش داخلی را از متن پیرامون جدا می‌کند و ممکن است عمدی باشد.", detailEn: "Isolates an embedded direction from surrounding text and may be intentional." },
  0x2069: { kind: "bidi-control", labelFa: "پایان جداساز جهت (PDI)", labelEn: "Pop directional isolate (PDI)", detailFa: "بازهٔ جداسازی جهت‌دار را می‌بندد و ممکن است عمدی باشد.", detailEn: "Closes a directional isolate and may be intentional." },
  0x200b: { kind: "invisible-format", labelFa: "فاصلهٔ بدون عرض (ZWSP)", labelEn: "Zero-width space (ZWSP)", detailFa: "نامرئی است و می‌تواند در شکستن واژه یا جست‌وجوی دقیق اثر بگذارد.", detailEn: "Invisible; it can affect word breaking or exact matching." },
  0x200c: { kind: "invisible-format", labelFa: "نیم‌فاصله (ZWNJ)", labelEn: "Zero-width non-joiner (ZWNJ)", detailFa: "در املای فارسی معمولاً کاربرد درست دارد؛ حذفش نکنید.", detailEn: "Often intentional in Persian orthography; do not remove it." },
  0x200d: { kind: "invisible-format", labelFa: "اتصال‌دهندهٔ بدون عرض (ZWJ)", labelEn: "Zero-width joiner (ZWJ)", detailFa: "می‌تواند در شکل‌دهی خط یا توالی ایموجی لازم باشد.", detailEn: "May be required for script shaping or emoji sequences." },
  0x2060: { kind: "invisible-format", labelFa: "اتصال‌دهندهٔ واژه (WJ)", labelEn: "Word joiner (WJ)", detailFa: "نامرئی است و از شکستن خط در یک نقطه جلوگیری می‌کند.", detailEn: "Invisible; prevents a line break at its position." },
  0xfeff: { kind: "invisible-format", labelFa: "نشانگر BOM / بدون عرض", labelEn: "BOM / zero-width no-break space", detailFa: "ممکن است در ابتدای متن نقش BOM داشته باشد؛ محل و زمینه را بررسی کنید.", detailEn: "May be a BOM at the beginning of text; review its position and context." },
  0xfffd: { kind: "replacement", labelFa: "نویسهٔ جایگزین (�)", labelEn: "Replacement character (�)", detailFa: "معمولاً نشان می‌دهد بخشی از متن هنگام رمزگشایی یا OCR قابل‌بازیابی نبوده است.", detailEn: "Often indicates text that could not be recovered during decoding or OCR." },
};

function formatCodePoint(value: number): string {
  return `U+${value.toString(16).toUpperCase().padStart(value <= 0xffff ? 4 : 5, "0")}`;
}

export function inspectUnicode(text: string): UnicodeInspection {
  const counts = new Map<number, number>();
  let codePointCount = 0;
  for (const character of text) {
    codePointCount += 1;
    const value = character.codePointAt(0);
    if (value !== undefined && CHARACTER_DETAILS[value]) counts.set(value, (counts.get(value) || 0) + 1);
  }

  const findings = [...counts.entries()].map(([value, count]) => ({
    character: String.fromCodePoint(value),
    codePoint: formatCodePoint(value),
    ...CHARACTER_DETAILS[value],
    count,
  }));
  findings.sort((a, b) => a.kind.localeCompare(b.kind) || a.codePoint.localeCompare(b.codePoint));

  return { codePointCount, utf16UnitCount: text.length, findings };
}
