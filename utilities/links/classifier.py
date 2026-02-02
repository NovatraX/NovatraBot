import os
from typing import Optional, Tuple

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

CLASSIFICATION_PROMPT = """Analyze this link and provide:
1. A category classification
2. A brief context summary explaining what this link is about and why it might be useful

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

Respond in this exact format (2 lines only):
CATEGORY: <category_name>
CONTEXT: <1-2 sentence summary of what this link contains and its purpose>"""


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


async def classify_link(
    url: str,
    domain: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    site_name: Optional[str] = None,
):
    client, model = _build_classifier_client()
    if not client:
        return "other", None

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
            max_tokens=150,
            temperature=0,
        )
        content = response.choices[0].message.content.strip()

        category = "other"
        context = None

        for line in content.split("\n"):
            line = line.strip()
            if line.upper().startswith("CATEGORY:"):
                cat = line.split(":", 1)[1].strip().lower()
                if cat in LINK_CATEGORIES:
                    category = cat
            elif line.upper().startswith("CONTEXT:"):
                context = line.split(":", 1)[1].strip()

        return category, context
    except Exception:
        return "other", None
