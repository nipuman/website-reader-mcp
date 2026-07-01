from unittest.mock import AsyncMock, patch

import pytest

from app.services.article_extractor import (
    EXTRACTION_FAILED_MESSAGE,
    prepare_article_summary,
)
from app.services.fetcher import FetchError, FetchResponse

SAMPLE_ARTICLE_HTML = """
<html lang="en">
  <head>
    <title>Summary Article</title>
    <meta name="description" content="A page to summarize" />
    <meta property="og:site_name" content="Example" />
  </head>
  <body>
    <article>
      <h1>Summary Article</h1>
      <p>
        This is a reasonably long article body with enough text for the extraction
        library to treat it as the main content that should be summarized later.
      </p>
      <p>
        A second paragraph provides additional substance and context so the article
        extraction produces a usable block of text for the summary prompt.
      </p>
    </article>
  </body>
</html>
"""


def _response(url: str = "https://example.com/article") -> FetchResponse:
    return FetchResponse(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=SAMPLE_ARTICLE_HTML,
    )


@pytest.mark.asyncio
async def test_prepare_article_summary_success():
    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(return_value=_response()),
    ):
        result = await prepare_article_summary("https://example.com/article", max_words=120)

    assert result.error is None
    assert result.url == "https://example.com/article"
    assert result.title == "Summary Article"
    assert result.text is not None
    assert result.content_length == len(result.text)
    assert result.summary_prompt is not None
    assert "120 words" in result.summary_prompt
    assert result.text in result.summary_prompt


@pytest.mark.asyncio
async def test_prepare_article_summary_rejects_invalid_url():
    result = await prepare_article_summary("not-a-url")

    assert result.error is not None
    assert result.summary_prompt is None
    assert result.text is None


@pytest.mark.asyncio
async def test_prepare_article_summary_handles_extraction_failure():
    response = FetchResponse(
        url="https://example.com/empty",
        final_url="https://example.com/empty",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body="<html><head><title>Empty</title></head><body></body></html>",
    )
    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(return_value=response),
    ):
        result = await prepare_article_summary("https://example.com/empty")

    assert result.error == EXTRACTION_FAILED_MESSAGE
    assert result.summary_prompt is None


@pytest.mark.asyncio
async def test_prepare_article_summary_handles_fetch_error():
    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(side_effect=FetchError("Too many redirects while fetching the URL.")),
    ):
        result = await prepare_article_summary("https://example.com/loop")

    assert result.error == "Too many redirects while fetching the URL."
    assert result.summary_prompt is None
