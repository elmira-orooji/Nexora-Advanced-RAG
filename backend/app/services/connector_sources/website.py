import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from collections.abc import Iterator
from pathlib import Path
from . import transport
from .contracts import ConnectorSyncError, SourceSnapshot, ALLOWED_EXTENSIONS

class TextHTMLParser(HTMLParser):
    def __init__(self): super().__init__(); self.parts: list[str] = []; self.skip = 0; self.title = ""
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}: self.skip += 1
        if tag in {"p", "br", "h1", "h2", "h3", "li", "article", "section"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

def _website(source_url: str) -> SourceSnapshot:
    data, content_type, final_url = transport._fetch(source_url)
    text = data.decode("utf-8", errors="replace")
    title = urlparse(final_url).hostname or "Website"
    if content_type == "text/html":
        match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        if match: title = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()[:255]
        parser = TextHTMLParser(); parser.feed(text); text = re.sub(r"\n{3,}", "\n\n", "".join(parser.parts)); text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 50: raise ConnectorSyncError("The web page contains too little readable text")

    def _iter() -> Iterator[tuple[str, str, str, str]]:
        yield (final_url, title, text, final_url)

    snapshot = SourceSnapshot(source_iterator=_iter(), observed_ids={final_url}, complete=True)
    return snapshot
