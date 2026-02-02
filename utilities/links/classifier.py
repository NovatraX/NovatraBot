import os
from typing import Optional

from openai import AsyncOpenAI

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

CLASSIFICATION_PROMPT = """Classify this link into exactly ONE category based on the metadata provided.

Categories:
- code: GitHub, GitLab, code repositories, programming projects
- documentation: API docs, wikis, technical references, manuals
- video: YouTube, Vimeo, video content platforms
- article: Blog posts, essays, written content, Medium
- social: Twitter/X, LinkedIn, social media posts
- news: News sites, press releases, current events
- tool: SaaS products, utilities, online tools, apps
- design: Figma, Dribbble, design resources, UI/UX
- learning: Courses, tutorials, educational platforms
- other: Anything that doesn't fit above

Link info:
- URL: {url}
- Domain: {domain}
- Title: {title}
- Description: {description}
- Site Name: {site_name}

Respond with ONLY the category name, nothing else."""


def _build_classifier_client() -> tuple[Optional[AsyncOpenAI], str]:
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


async def classify_link(
    url: str,
    domain: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    site_name: Optional[str] = None,
) -> str:
    """Classify a link using AI. Returns category string."""
    client, model = _build_classifier_client()
    if not client:
        return "other"

    prompt = CLASSIFICATION_PROMPT.format(
        url=url,
        domain=domain or "",
        title=title or "Unknown",
        description=description or "None",
        site_name=site_name or "Unknown",
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0,
        )
        category = response.choices[0].message.content.strip().lower()
        if category in LINK_CATEGORIES:
            return category
        return "other"
    except Exception:
        return "other"
