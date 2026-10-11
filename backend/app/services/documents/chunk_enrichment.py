import re
from collections import Counter

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06ff]{3,}")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "into", "about", "your", "have", "has", "will", "can",
    "این", "آن", "برای", "است", "هست", "های", "هایی", "شود", "شده", "کرد", "یک", "در", "از", "به", "با", "که", "را", "روی", "بر", "می",
}


def enrich_chunk(content: str, keyword_limit: int = 8) -> tuple[list[str], list[str]]:
    tokens = [token.strip("_- ") for token in TOKEN_RE.findall(content)]
    normalized = [token.lower() for token in tokens if token.lower() not in STOPWORDS]
    counts = Counter(normalized)
    first_seen = {token: index for index, token in enumerate(normalized)}
    ranked = sorted(counts, key=lambda token: (-counts[token], first_seen[token], -len(token)))[:keyword_limit]
    display = []
    for keyword in ranked:
        original = next((token for token in tokens if token.lower() == keyword), keyword)
        display.append(original)
    if not display:
        return [], []
    persian = bool(re.search(r"[\u0600-\u06ff]", content))
    primary = display[0]
    secondary = display[1] if len(display) > 1 else display[0]
    questions = (
        [f"این بخش چه اطلاعاتی دربارهٔ {primary} ارائه می‌دهد؟", f"ارتباط {primary} و {secondary} در این متن چیست؟", f"مهم‌ترین نکات این بخش دربارهٔ {primary} کدام‌اند؟"]
        if persian else
        [f"What does this section explain about {primary}?", f"How are {primary} and {secondary} related in this text?", f"What are the key points about {primary} in this section?"]
    )
    return display, questions
