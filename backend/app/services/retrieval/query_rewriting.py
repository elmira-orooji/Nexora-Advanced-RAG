import re

REFERENCE_TERMS = {
    "it", "that", "this", "they", "them", "those", "these", "he", "she", "its", "their",
    "former", "latter", "above", "previous", "same", "more", "else",
    "این", "آن", "اون", "همین", "همان", "قبلی", "بالا", "بیشتر", "ایشان", "آنها", "آن‌ها",
    "او", "وی", "مورد", "درباره", "چطور", "چرا",
}
FOLLOW_UP_PATTERNS = (
    re.compile(r"^(and|also|what about|how about|why|when|where|who|which|explain more|tell me more)\b", re.I),
    re.compile(r"^(و|همچنین|حالا|پس|چرا|چطور|کی|کجا|کدام|بیشتر|توضیح بیشتر|در مورد)\b"),
)


def should_rewrite(question: str, history: list[dict[str, str]]) -> bool:
    if not history:
        return False
    normalized = question.strip().lower()
    if any(pattern.search(normalized) for pattern in FOLLOW_UP_PATTERNS):
        return True
    terms = set(re.findall(r"[\w\u0600-\u06ff]+", normalized))
    if terms & REFERENCE_TERMS:
        return True
    return len(terms) <= 5
