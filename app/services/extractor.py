import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

REMOVED_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "nav",
    "footer",
    "header",
    "form",
}


@dataclass(frozen=True)
class ExtractedContent:
    title: str | None
    description: str | None
    text: str


def _extract_title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        return title or None
    return None


def _extract_description(soup: BeautifulSoup) -> str | None:
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        if name in {"description", "og:description", "twitter:description"}:
            content = meta.get("content")
            if content and content.strip():
                return content.strip()
    return None


def _remove_unwanted_elements(root: Tag) -> None:
    for tag_name in REMOVED_TAGS:
        for element in root.find_all(tag_name):
            element.decompose()


def _find_content_root(soup: BeautifulSoup) -> Tag:
    for selector in ("main", "article"):
        element = soup.find(selector)
        if element:
            return element

    body = soup.body
    if body:
        return body

    return soup


def _normalize_block_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _collect_text(element: Tag) -> str:
    block_tags = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
    }

    parts: list[str] = []

    def walk(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                parts.append(text)
            return

        if not isinstance(node, Tag):
            return

        if node.name in block_tags:
            before_len = len(parts)
            for child in node.children:
                walk(child)

            if len(parts) > before_len and parts and not parts[-1].endswith("\n\n"):
                parts.append("\n\n")
            return

        for child in node.children:
            walk(child)

    walk(element)

    joined = " ".join(part for part in parts if part != "\n\n")
    joined = re.sub(r" +", " ", joined)
    joined = re.sub(r" *\n\n *", "\n\n", joined)
    return _normalize_block_text(joined)


def extract_readable_content(html: str) -> ExtractedContent:
    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup)
    description = _extract_description(soup)

    content_root = _find_content_root(soup)
    _remove_unwanted_elements(content_root)
    text = _collect_text(content_root)

    return ExtractedContent(title=title, description=description, text=text)


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip() + "…", True
