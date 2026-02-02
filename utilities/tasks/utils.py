import hashlib
import re
from typing import Optional

DEFAULT_PRIORITY = "medium_priority"

_PRIORITY_ALIASES = {
    "urgent": "urgent",
    "high": "high_priority",
    "high_priority": "high_priority",
    "highpriority": "high_priority",
    "medium": "medium_priority",
    "medium_priority": "medium_priority",
    "mediumpriority": "medium_priority",
    "low": "low_priority",
    "low_priority": "low_priority",
    "lowpriority": "low_priority",
}

_PRIORITY_ORDER = {
    "urgent": 0,
    "high_priority": 1,
    "medium_priority": 2,
    "low_priority": 3,
}

_MESSAGE_LINK_RE = re.compile(r"https?://discord\.com/channels/\d+/\d+/\d+")


def clean_task_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def normalize_priority(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_PRIORITY
    key = value.strip().lower().replace(" ", "_")
    return _PRIORITY_ALIASES.get(key, DEFAULT_PRIORITY)


def priority_rank(value: Optional[str]) -> int:
    return _PRIORITY_ORDER.get(normalize_priority(value), 99)


def extract_message_link(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = _MESSAGE_LINK_RE.search(text)
    return match.group(0) if match else None


def extract_message_id(link: Optional[str]) -> Optional[int]:
    if not link:
        return None
    try:
        return int(link.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        return None


def dedupe_key(user_id: int, source_message_id: Optional[int], text: str) -> str:
    normalized = clean_task_text(text).lower()
    raw = f"{user_id}|{source_message_id or 0}|{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
