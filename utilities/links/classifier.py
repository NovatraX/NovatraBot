import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from openai import AsyncOpenAI
from trafilatura import extract as trafilatura_extract
from trafilatura import extract_metadata as trafilatura_extract_metadata

from utilities.links.utils import parse_metadata

LINK_CATEGORIES = [
    "code",
    "documentation",
    "video",
    "article",
    "social",
    "news",
    "tool",
    "design",
    "learning",
    "other",
]

METADATA_TEXT_LIMIT = 3000
CLASSIFICATION_TEXT_LIMIT = 1500

METADATA_PROMPT = """You generate clean, compact link metadata.
Return JSON only with keys: title, description, site_name.
Rules:
- title: concise, <= 120 chars, no trailing site name unless part of the title.
- description: 1-2 sentences, <= 240 chars.
- site_name: short publisher/product name.
- If unsure, return null for that field.

URL: {url}
Domain: {domain}
Raw title: {raw_title}
Raw description: {raw_description}
Raw site name: {raw_site}
Extracted text: {text_excerpt}
"""

CLASSIFICATION_PROMPT = """Classify the link and summarize its purpose.
Return JSON only with keys: category, context.
Categories: code, documentation, video, article, social, news, tool, design, learning, other.
context: 1-2 sentences on what the link contains and why it might be useful.

URL: {url}
Domain: {domain}
Title: {title}
Description: {description}
Site name: {site_name}
Content excerpt: {text_excerpt}
"""


@dataclass(frozen=True)
class LinkMetadata:
    title: Optional[str] = None
    description: Optional[str] = None
    site_name: Optional[str] = None
    image_url: Optional[str] = None


def _build_classifier_client() -> Tuple[Optional[AsyncOpenAI], str]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None, ""

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    headers = {}
    referer = os.getenv("OPENROUTER_HTTP_REFERER")
    if referer:
        headers["HTTP-Referer"] = referer
    title = os.getenv("OPENROUTER_APP_TITLE")
    if title:
        headers["X-Title"] = title

    client_kwargs = {"api_key": api_key, "base_url": base_url}
    if headers:
        client_kwargs["default_headers"] = headers

    return AsyncOpenAI(**client_kwargs), model


def _clean_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = " ".join(str(value).split()).strip()
    return cleaned or None


def _truncate(value: Optional[str], limit: int) -> Optional[str]:
    if not value:
        return None
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _parse_json_payload(content: str) -> Optional[Dict[str, Any]]:
    if not content:
        return None
    payload = content.strip()
    if payload.startswith("```"):
        payload = payload.strip("`").strip()
        if payload.lower().startswith("json"):
            payload = payload[4:].strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", payload, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _merge_metadata(primary: LinkMetadata, fallback: LinkMetadata) -> LinkMetadata:
    return LinkMetadata(
        title=primary.title or fallback.title,
        description=primary.description or fallback.description,
        site_name=primary.site_name or fallback.site_name,
        image_url=primary.image_url or fallback.image_url,
    )


def _extract_raw_metadata(
    html: Optional[str],
    url: str,
) -> Tuple[LinkMetadata, Optional[str]]:
    if not html:
        return LinkMetadata(), None

    og_meta = parse_metadata(html)
    trafi_meta = None
    trafi_text = None
    try:
        trafi_meta = trafilatura_extract_metadata(html, default_url=url)
    except Exception:
        trafi_meta = None
    try:
        trafi_text = trafilatura_extract(
            html,
            url=url,
            include_comments=False,
            include_links=False,
            include_images=False,
        )
    except Exception:
        trafi_text = None

    title = _clean_value(getattr(trafi_meta, "title", None)) or _clean_value(
        og_meta.get("title")
    )
    description = _clean_value(
        getattr(trafi_meta, "description", None)
    ) or _clean_value(og_meta.get("description"))
    site_name = _clean_value(getattr(trafi_meta, "sitename", None)) or _clean_value(
        og_meta.get("site_name")
    )
    image_url = _clean_value(og_meta.get("image_url")) or _clean_value(
        getattr(trafi_meta, "image", None)
    )

    return (
        LinkMetadata(
            title=title,
            description=description,
            site_name=site_name,
            image_url=image_url,
        ),
        _clean_value(trafi_text),
    )


async def _generate_metadata_with_llm(
    client: Optional[AsyncOpenAI],
    model: str,
    url: str,
    domain: str,
    raw: LinkMetadata,
    text: Optional[str],
) -> LinkMetadata:
    if not client:
        return raw

    prompt = METADATA_PROMPT.format(
        url=url,
        domain=domain or "",
        raw_title=raw.title or "None",
        raw_description=raw.description or "None",
        raw_site=raw.site_name or "None",
        text_excerpt=_truncate(text, METADATA_TEXT_LIMIT) or "None",
    )
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0,
        )
        payload = _parse_json_payload(response.choices[0].message.content.strip())
        if not payload:
            return raw
        llm_meta = LinkMetadata(
            title=_clean_value(payload.get("title")),
            description=_clean_value(payload.get("description")),
            site_name=_clean_value(payload.get("site_name")),
            image_url=None,
        )
        return _merge_metadata(llm_meta, raw)
    except Exception:
        return raw


async def _classify_with_llm(
    client: Optional[AsyncOpenAI],
    model: str,
    url: str,
    domain: str,
    metadata: LinkMetadata,
    text: Optional[str],
) -> Tuple[str, Optional[str]]:
    if not client:
        return "other", None

    prompt = CLASSIFICATION_PROMPT.format(
        url=url,
        domain=domain or "",
        title=metadata.title or "Unknown",
        description=metadata.description or "None",
        site_name=metadata.site_name or "Unknown",
        text_excerpt=_truncate(text, CLASSIFICATION_TEXT_LIMIT) or "None",
    )
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=180,
            temperature=0,
        )
        payload = _parse_json_payload(response.choices[0].message.content.strip())
        if not payload:
            return "other", None
        category = str(payload.get("category", "")).strip().lower()
        if category not in LINK_CATEGORIES:
            category = "other"
        context = _clean_value(payload.get("context"))
        return category, context
    except Exception:
        return "other", None


async def analyze_link(
    url: str,
    domain: str,
    html: Optional[str],
) -> Tuple[LinkMetadata, str, Optional[str]]:
    raw_meta, text = _extract_raw_metadata(html, url)
    client, model = _build_classifier_client()
    llm_meta = await _generate_metadata_with_llm(
        client=client,
        model=model,
        url=url,
        domain=domain,
        raw=raw_meta,
        text=text,
    )
    category, context = await _classify_with_llm(
        client=client,
        model=model,
        url=url,
        domain=domain,
        metadata=llm_meta,
        text=text,
    )
    return llm_meta, category, context


async def classify_link(
    url: str,
    domain: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    site_name: Optional[str] = None,
    text: Optional[str] = None,
):
    client, model = _build_classifier_client()
    metadata = LinkMetadata(
        title=_clean_value(title),
        description=_clean_value(description),
        site_name=_clean_value(site_name),
    )
    return await _classify_with_llm(
        client=client,
        model=model,
        url=url,
        domain=domain,
        metadata=metadata,
        text=_clean_value(text),
    )
