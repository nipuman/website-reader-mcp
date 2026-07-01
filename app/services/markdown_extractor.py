"""HTML to Markdown conversion.

Prefers trafilatura's Markdown output (good boilerplate removal) and falls
back to a lightweight BeautifulSoup-based converter when trafilatura cannot
find usable content.
"""

import re

import trafilatura
from bs4 import BeautifulSoup, NavigableString, Tag

from app.config import Settings, get_settings
from app.schemas import FetchMarkdownResult
from app.services.extractor import (
    _find_content_root,
    _remove_unwanted_elements,
)
from app.services.fetcher import FetchError, fetch_url_content
from app.services.metadata_extractor import extract_page_metadata

EXTRACTION_METHOD_TRAFILATURA = "trafilatura"
EXTRACTION_METHOD_BEAUTIFULSOUP = "beautifulsoup4"
MARKDOWN_FAILED_MESSAGE = "Could not extract readable content to convert to Markdown."


def _normalize_markdown(markdown: str) -> str:
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _trafilatura_markdown(html: str, url: str | None = None) -> str | None:
    try:
        markdown = trafilatura.extract(
            html,
            url=url,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            include_links=True,
            include_images=False,
            favor_recall=True,
        )
    except Exception:  # noqa: BLE001 - never let extraction crash the tool
        return None

    if not markdown or not markdown.strip():
        return None

    return _normalize_markdown(markdown)


def _inline_markdown(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return str(node)

    if not isinstance(node, Tag):
        return ""

    name = node.name

    if name in {"strong", "b"}:
        return f"**{_children_inline(node).strip()}**"
    if name in {"em", "i"}:
        return f"*{_children_inline(node).strip()}*"
    if name == "code":
        return f"`{node.get_text().strip()}`"
    if name == "br":
        return "\n"
    if name == "a":
        text = _children_inline(node).strip() or node.get_text().strip()
        href = (node.get("href") or "").strip()
        if href and text:
            return f"[{text}]({href})"
        return text

    return _children_inline(node)


def _children_inline(node: Tag) -> str:
    return "".join(_inline_markdown(child) for child in node.children)


def _block_markdown(node: Tag, depth: int = 0) -> list[str]:
    blocks: list[str] = []
    heading_levels = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                blocks.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        name = child.name

        if name in heading_levels:
            text = _children_inline(child).strip()
            if text:
                blocks.append(f"{'#' * heading_levels[name]} {text}")
        elif name == "p":
            text = _inline_markdown(child).strip()
            if text:
                blocks.append(text)
        elif name in {"ul", "ol"}:
            blocks.extend(_list_markdown(child, ordered=name == "ol", depth=depth))
        elif name == "pre":
            code = child.get_text().rstrip("\n")
            if code.strip():
                blocks.append(f"```\n{code}\n```")
        elif name == "blockquote":
            inner = _block_markdown(child, depth)
            quoted = "\n".join(f"> {line}" for line in "\n\n".join(inner).split("\n"))
            if quoted.strip("> \n"):
                blocks.append(quoted)
        elif name in {"div", "section", "article", "main", "figure", "figcaption"}:
            blocks.extend(_block_markdown(child, depth))
        else:
            text = _inline_markdown(child).strip()
            if text:
                blocks.append(text)

    return blocks


def _list_markdown(node: Tag, ordered: bool, depth: int) -> list[str]:
    lines: list[str] = []
    indent = "  " * depth
    index = 1
    for item in node.find_all("li", recursive=False):
        marker = f"{index}." if ordered else "-"
        text = _inline_markdown_without_lists(item).strip()
        lines.append(f"{indent}{marker} {text}".rstrip())
        for sub in item.find_all(["ul", "ol"], recursive=False):
            nested = _list_markdown(sub, ordered=sub.name == "ol", depth=depth + 1)
            lines.extend(nested)
        index += 1
    if not lines:
        return []
    return ["\n".join(lines)]


def _inline_markdown_without_lists(item: Tag) -> str:
    parts: list[str] = []
    for child in item.children:
        if isinstance(child, Tag) and child.name in {"ul", "ol"}:
            continue
        parts.append(_inline_markdown(child))
    return "".join(parts)


def _bs4_markdown(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    content_root = _find_content_root(soup)
    _remove_unwanted_elements(content_root)

    blocks = _block_markdown(content_root)
    markdown = "\n\n".join(block for block in blocks if block.strip())
    markdown = _normalize_markdown(markdown)
    return markdown or None


def html_to_markdown(html: str, url: str | None = None) -> tuple[str | None, str]:
    markdown = _trafilatura_markdown(html, url=url)
    if markdown:
        return markdown, EXTRACTION_METHOD_TRAFILATURA

    fallback = _bs4_markdown(html)
    if fallback:
        return fallback, EXTRACTION_METHOD_BEAUTIFULSOUP

    return None, EXTRACTION_METHOD_TRAFILATURA


def _truncate_markdown(markdown: str, max_chars: int) -> tuple[str, bool]:
    if len(markdown) <= max_chars:
        return markdown, False
    return markdown[:max_chars].rstrip() + "\n\n…", True


async def get_markdown(
    url: str,
    max_chars: int | None = None,
    settings: Settings | None = None,
) -> FetchMarkdownResult:
    settings = settings or get_settings()
    cleaned_url = url.strip()

    try:
        response = await fetch_url_content(cleaned_url, settings)
    except FetchError as exc:
        return FetchMarkdownResult(url=cleaned_url or url, error=str(exc))

    markdown, method = html_to_markdown(response.body, url=response.final_url)
    if not markdown:
        return FetchMarkdownResult(
            url=response.url,
            final_url=response.final_url,
            error=MARKDOWN_FAILED_MESSAGE,
            extraction_method=method,
        )

    try:
        metadata = extract_page_metadata(response.body, url=response.final_url)
        title = metadata.get("title")
    except Exception:  # noqa: BLE001 - title is best-effort
        title = None

    char_limit = max_chars if max_chars is not None else settings.max_response_chars
    markdown, truncated = _truncate_markdown(markdown, char_limit)

    return FetchMarkdownResult(
        url=response.url,
        final_url=response.final_url,
        title=title,
        markdown=markdown,
        content_length=len(markdown),
        truncated=truncated,
        extraction_method=method,
    )
