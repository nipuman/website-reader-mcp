import re

import trafilatura

from app.config import Settings, get_settings
from app.schemas import ExtractArticleResult
from app.services.extractor import extract_readable_content, truncate_text
from app.services.fetcher import FetchError, fetch_url_content

EXTRACTION_METHOD_TRAFILATURA = "trafilatura"
EXTRACTION_METHOD_BEAUTIFULSOUP = "beautifulsoup4"
EXTRACTION_FAILED_MESSAGE = "Could not extract readable article content from this page."


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_metadata_dict(html: str, url: str | None = None) -> dict[str, str | None]:
    metadata = trafilatura.extract_metadata(html, default_url=url)
    if metadata is None:
        return {
            "title": None,
            "author": None,
            "date": None,
            "description": None,
            "site_name": None,
            "language": None,
        }

    return {
        "title": metadata.title or None,
        "author": metadata.author or None,
        "date": metadata.date or None,
        "description": metadata.description or None,
        "site_name": metadata.sitename or None,
        "language": metadata.language or None,
    }


def _extract_with_trafilatura(html: str, url: str | None = None) -> str | None:
    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )
    if not text or not text.strip():
        return None

    return normalize_whitespace(text)


def _extract_with_beautifulsoup(html: str) -> str | None:
    extracted = extract_readable_content(html)
    if not extracted.text.strip():
        return None

    return extracted.text


def extract_article_text(html: str, url: str | None = None) -> tuple[str | None, str]:
    text = _extract_with_trafilatura(html, url=url)
    if text:
        return text, EXTRACTION_METHOD_TRAFILATURA

    fallback_text = _extract_with_beautifulsoup(html)
    if fallback_text:
        return fallback_text, EXTRACTION_METHOD_BEAUTIFULSOUP

    return None, EXTRACTION_METHOD_TRAFILATURA


def _error_result(url: str, error: str, extraction_method: str = EXTRACTION_METHOD_TRAFILATURA) -> ExtractArticleResult:
    return ExtractArticleResult(
        url=url,
        error=error,
        text=None,
        extraction_method=extraction_method,
    )


async def extract_article_content(
    url: str,
    max_chars: int | None = 20000,
    include_metadata: bool = True,
    settings: Settings | None = None,
) -> ExtractArticleResult:
    settings = settings or get_settings()
    cleaned_url = url.strip()

    try:
        response = await fetch_url_content(cleaned_url, settings)
    except FetchError as exc:
        return _error_result(cleaned_url, str(exc))

    text, extraction_method = extract_article_text(response.body, url=response.final_url)
    if not text:
        return _error_result(response.final_url, EXTRACTION_FAILED_MESSAGE, extraction_method)

    char_limit = max_chars if max_chars is not None else 20000
    truncated_text, truncated = truncate_text(text, char_limit)

    metadata = extract_metadata_dict(response.body, url=response.final_url) if include_metadata else {}

    return ExtractArticleResult(
        url=response.final_url,
        title=metadata.get("title"),
        author=metadata.get("author"),
        date=metadata.get("date"),
        description=metadata.get("description"),
        site_name=metadata.get("site_name"),
        language=metadata.get("language"),
        text=truncated_text,
        text_length=len(truncated_text),
        truncated=truncated,
        extraction_method=extraction_method,
    )
