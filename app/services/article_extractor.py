import re

import trafilatura

from app.config import Settings, get_settings
from app.schemas import ExtractArticleResult, SummarizeArticleResult
from app.services.extractor import extract_readable_content, truncate_text
from app.services.fetcher import FetchError, fetch_url_content
from app.services.markdown_extractor import html_to_markdown
from app.services.metadata_extractor import extract_page_metadata

EXTRACTION_METHOD_TRAFILATURA = "trafilatura"
EXTRACTION_METHOD_BEAUTIFULSOUP = "beautifulsoup4"
EXTRACTION_FAILED_MESSAGE = "Could not extract readable article content from this page."

SUMMARY_MAX_CHARS = 12000


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_with_trafilatura(html: str, url: str | None = None) -> str | None:
    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
    except Exception:  # noqa: BLE001 - never crash on malformed markup
        return None

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


def _safe_metadata(html: str, url: str | None) -> dict[str, str | None]:
    try:
        return extract_page_metadata(html, url=url)
    except Exception:  # noqa: BLE001 - metadata is best-effort
        return {}


def _error_result(
    url: str,
    error: str,
    final_url: str | None = None,
    extraction_method: str = EXTRACTION_METHOD_TRAFILATURA,
) -> ExtractArticleResult:
    return ExtractArticleResult(
        url=url,
        final_url=final_url,
        error=error,
        text=None,
        extraction_method=extraction_method,
    )


async def extract_article_content(
    url: str,
    max_chars: int | None = 20000,
    include_metadata: bool = True,
    include_markdown: bool = True,
    settings: Settings | None = None,
) -> ExtractArticleResult:
    settings = settings or get_settings()
    cleaned_url = url.strip()

    try:
        response = await fetch_url_content(cleaned_url, settings)
    except FetchError as exc:
        return _error_result(cleaned_url or url, str(exc))

    text, extraction_method = extract_article_text(response.body, url=response.final_url)
    if not text:
        return _error_result(
            response.url,
            EXTRACTION_FAILED_MESSAGE,
            final_url=response.final_url,
            extraction_method=extraction_method,
        )

    char_limit = max_chars if max_chars is not None else 20000
    truncated_text, truncated = truncate_text(text, char_limit)

    markdown: str | None = None
    if include_markdown:
        markdown_text, _ = html_to_markdown(response.body, url=response.final_url)
        if markdown_text:
            markdown, _ = truncate_text(markdown_text, char_limit)

    metadata = _safe_metadata(response.body, response.final_url) if include_metadata else {}

    return ExtractArticleResult(
        url=response.url,
        final_url=response.final_url,
        title=metadata.get("title"),
        author=metadata.get("author"),
        published_date=metadata.get("published_date"),
        description=metadata.get("description"),
        site_name=metadata.get("site_name"),
        language=metadata.get("language"),
        text=truncated_text,
        markdown=markdown,
        content_length=len(truncated_text),
        truncated=truncated,
        extraction_method=extraction_method,
    )


def build_summary_prompt(
    title: str | None,
    text: str,
    language: str | None = None,
    max_words: int = 150,
) -> str:
    """Build an LLM-agnostic prompt the chat backend can send to its own model."""
    heading = title.strip() if title else "the following article"
    language_hint = (
        f" Write the summary in the same language as the article ({language})."
        if language
        else " Write the summary in the same language as the article."
    )

    return (
        f"Summarize {heading} in at most {max_words} words. "
        "Focus on the key points, findings and conclusions. "
        "Use clear, neutral language and do not add information that is not in the text."
        f"{language_hint}\n\n"
        "Article content:\n"
        f"{text}"
    )


async def prepare_article_summary(
    url: str,
    max_chars: int | None = SUMMARY_MAX_CHARS,
    max_words: int = 150,
    settings: Settings | None = None,
) -> SummarizeArticleResult:
    settings = settings or get_settings()
    cleaned_url = url.strip()

    article = await extract_article_content(
        url=cleaned_url or url,
        max_chars=max_chars,
        include_metadata=True,
        include_markdown=False,
        settings=settings,
    )

    if article.error or not article.text:
        return SummarizeArticleResult(
            url=article.url,
            final_url=article.final_url,
            error=article.error or EXTRACTION_FAILED_MESSAGE,
            extraction_method=article.extraction_method,
        )

    summary_prompt = build_summary_prompt(
        title=article.title,
        text=article.text,
        language=article.language,
        max_words=max_words,
    )

    return SummarizeArticleResult(
        url=article.url,
        final_url=article.final_url,
        title=article.title,
        author=article.author,
        published_date=article.published_date,
        description=article.description,
        text=article.text,
        content_length=article.content_length,
        truncated=article.truncated,
        summary_prompt=summary_prompt,
        extraction_method=article.extraction_method,
    )
