import re
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse

_URL_RE = re.compile(r"https?://[^\s<>\]]+")
_TRAILING_PUNCT = '.,;:!?)"]}'
_IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".gifv",
    ".webp",
    ".bmp",
    ".tiff",
    ".svg",
}
_VIDEO_EXTS = {
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".avi",
    ".wmv",
    ".m4v",
}


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    urls = []
    for match in _URL_RE.findall(text):
        cleaned = match.strip().strip("<>")
        cleaned = cleaned.rstrip(_TRAILING_PUNCT)
        if cleaned:
            urls.append(cleaned)
    # Dedupe while preserving order.
    return list(dict.fromkeys(urls))


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "",
            parsed.params or "",
            parsed.query or "",
            "",
        )
    )


def domain_for_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_media_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in _IMAGE_EXTS | _VIDEO_EXTS):
        return True
    netloc = parsed.netloc.lower()
    if any(host in netloc for host in ("media.discordapp.net", "cdn.discordapp.com")):
        return True
    if any(host in netloc for host in ("tenor.com", "giphy.com")):
        return True
    return False


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self._title_chunks: List[str] = []
        self._meta: Dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        if tag == "title":
            self._in_title = True
            return
        if tag != "meta":
            return
        attrs_dict = {key.lower(): value for key, value in attrs if key and value}
        key = attrs_dict.get("property") or attrs_dict.get("name")
        if not key:
            return
        value = attrs_dict.get("content")
        if not value:
            return
        self._meta[key.lower()] = value.strip()

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str):
        if self._in_title:
            self._title_chunks.append(data.strip())

    def build(self) -> Dict[str, str]:
        title = " ".join(chunk for chunk in self._title_chunks if chunk).strip()
        return {
            "title": title,
            "meta": self._meta,
        }


def parse_metadata(html: str) -> Dict[str, Optional[str]]:
    parser = _MetadataParser()
    parser.feed(html)
    payload = parser.build()
    meta = payload["meta"]
    title = (
        meta.get("og:title") or meta.get("twitter:title") or payload["title"] or None
    )
    description = (
        meta.get("og:description")
        or meta.get("twitter:description")
        or meta.get("description")
        or None
    )
    site_name = meta.get("og:site_name") or None
    image_url = meta.get("og:image") or meta.get("twitter:image") or None
    return {
        "title": title,
        "description": description,
        "site_name": site_name,
        "image_url": image_url,
    }
