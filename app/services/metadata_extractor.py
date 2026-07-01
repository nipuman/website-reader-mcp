"""Metadata extraction from HTML.

Combines trafilatura's metadata extraction with a BeautifulSoup pass over
Open Graph, Twitter card, JSON-LD and standard meta tags so that individual
fields degrade gracefully when a page only exposes some of them.
"""

import json
from urllib.parse import urljoin

import trafilatura
from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from app.schemas import ExtractMetadataResult
from app.services.fetcher import FetchError, fetch_url_content

ARTICLE_LD_TYPES = {
    "article",
    "newsarticle",
    "blogposting",
    "techarticle",
    "report",
    "webpage",
}


def _clean(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first(*values: object | None) -> str | None:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return None


def _meta_lookup(soup: BeautifulSoup) -> dict[str, str]:
    """Collect meta tag content keyed by lowercase name/property."""
    found: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        key = meta.get("property") or meta.get("name") or meta.get("itemprop")
        content = meta.get("content")
        if not key or content is None:
            continue
        key = key.strip().lower()
        content = content.strip()
        if key and content and key not in found:
            found[key] = content
    return found


def _extract_jsonld(soup: BeautifulSoup) -> dict[str, str | None]:
    """Pull useful fields out of JSON-LD blocks, favouring article types."""
    result: dict[str, str | None] = {}

    def author_name(value: object) -> str | None:
        if isinstance(value, str):
            return _clean(value)
        if isinstance(value, dict):
            return _clean(value.get("name"))
        if isinstance(value, list):
            names = [author_name(item) for item in value]
            names = [name for name in names if name]
            return ", ".join(names) if names else None
        return None

    def image_url(value: object) -> str | None:
        if isinstance(value, str):
            return _clean(value)
        if isinstance(value, dict):
            return _clean(value.get("url"))
        if isinstance(value, list) and value:
            return image_url(value[0])
        return None

    def consider(node: object) -> None:
        if not isinstance(node, dict):
            return

        node_type = node.get("@type")
        types: list[str] = []
        if isinstance(node_type, str):
            types = [node_type.lower()]
        elif isinstance(node_type, list):
            types = [str(item).lower() for item in node_type]

        is_article = any(item in ARTICLE_LD_TYPES for item in types)

        candidates = {
            "title": _first(node.get("headline"), node.get("name")),
            "description": _clean(node.get("description")),
            "author": author_name(node.get("author")),
            "published_date": _first(
                node.get("datePublished"),
                node.get("dateCreated"),
                node.get("dateModified"),
            ),
            "site_name": _clean(node.get("publisher", {}).get("name"))
            if isinstance(node.get("publisher"), dict)
            else None,
            "image": image_url(node.get("image")),
            "language": _clean(node.get("inLanguage")),
        }

        for field, candidate in candidates.items():
            if candidate is None:
                continue
            # Article-level nodes take priority over generic ones.
            if is_article or field not in result or result[field] is None:
                result[field] = candidate

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        nodes: list[object] = []
        if isinstance(data, list):
            nodes.extend(data)
        elif isinstance(data, dict):
            if isinstance(data.get("@graph"), list):
                nodes.extend(data["@graph"])
            else:
                nodes.append(data)

        for node in nodes:
            consider(node)

    return result


def _canonical_url(soup: BeautifulSoup, base_url: str | None) -> str | None:
    link = soup.find("link", rel=lambda value: value and "canonical" in value.lower())
    if link and link.get("href"):
        href = link["href"].strip()
        if href:
            return urljoin(base_url or "", href) if base_url else href
    return None


def _language(soup: BeautifulSoup) -> str | None:
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        return _clean(html_tag.get("lang"))
    return None


def _trafilatura_metadata(html: str, url: str | None) -> dict[str, str | None]:
    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
    except Exception:  # noqa: BLE001 - trafilatura may raise on malformed input
        metadata = None

    if metadata is None:
        return {}

    return {
        "title": _clean(metadata.title),
        "description": _clean(metadata.description),
        "author": _clean(metadata.author),
        "published_date": _clean(metadata.date),
        "site_name": _clean(metadata.sitename),
        "language": _clean(metadata.language),
        "image": _clean(metadata.image),
    }


def extract_page_metadata(html: str, url: str | None = None) -> dict[str, str | None]:
    """Extract a normalized metadata dict from HTML using every available signal."""
    soup = BeautifulSoup(html, "html.parser")
    meta = _meta_lookup(soup)
    jsonld = _extract_jsonld(soup)
    traf = _trafilatura_metadata(html, url)

    title_tag = soup.title.string.strip() if soup.title and soup.title.string else None

    title = _first(
        meta.get("og:title"),
        meta.get("twitter:title"),
        traf.get("title"),
        jsonld.get("title"),
        title_tag,
    )
    description = _first(
        meta.get("og:description"),
        meta.get("twitter:description"),
        meta.get("description"),
        traf.get("description"),
        jsonld.get("description"),
    )
    author = _first(
        meta.get("author"),
        meta.get("article:author"),
        meta.get("og:article:author"),
        meta.get("twitter:creator"),
        traf.get("author"),
        jsonld.get("author"),
    )
    published_date = _first(
        meta.get("article:published_time"),
        meta.get("og:article:published_time"),
        meta.get("article:modified_time"),
        meta.get("date"),
        meta.get("dc.date"),
        meta.get("dc.date.issued"),
        traf.get("published_date"),
        jsonld.get("published_date"),
    )
    site_name = _first(
        meta.get("og:site_name"),
        traf.get("site_name"),
        jsonld.get("site_name"),
    )
    language = _first(
        _language(soup),
        meta.get("og:locale"),
        traf.get("language"),
        jsonld.get("language"),
    )
    image = _first(
        meta.get("og:image"),
        meta.get("og:image:url"),
        meta.get("twitter:image"),
        meta.get("twitter:image:src"),
        traf.get("image"),
        jsonld.get("image"),
    )
    if image and url:
        image = urljoin(url, image)

    canonical_url = _canonical_url(soup, url)

    return {
        "title": title,
        "description": description,
        "author": author,
        "published_date": published_date,
        "site_name": site_name,
        "language": language,
        "image": image,
        "canonical_url": canonical_url,
    }


async def get_page_metadata(
    url: str,
    settings: Settings | None = None,
) -> ExtractMetadataResult:
    settings = settings or get_settings()
    cleaned_url = url.strip()

    try:
        response = await fetch_url_content(cleaned_url, settings)
    except FetchError as exc:
        return ExtractMetadataResult(url=cleaned_url or url, error=str(exc))

    try:
        metadata = extract_page_metadata(response.body, url=response.final_url)
    except Exception as exc:  # noqa: BLE001 - never crash on malformed markup
        return ExtractMetadataResult(
            url=response.url,
            final_url=response.final_url,
            error=f"Failed to parse metadata: {exc}",
        )

    return ExtractMetadataResult(
        url=response.url,
        final_url=response.final_url,
        title=metadata.get("title"),
        description=metadata.get("description"),
        author=metadata.get("author"),
        published_date=metadata.get("published_date"),
        site_name=metadata.get("site_name"),
        language=metadata.get("language"),
        image=metadata.get("image"),
        canonical_url=metadata.get("canonical_url"),
    )
