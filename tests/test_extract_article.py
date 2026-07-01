from unittest.mock import AsyncMock, patch

import pytest

from app.schemas import ExtractArticleResult
from app.services.article_extractor import (
    EXTRACTION_FAILED_MESSAGE,
    build_summary_prompt,
    extract_article_content,
    extract_article_text,
    normalize_whitespace,
)
from app.services.fetcher import FetchError, FetchResponse
from app.tools.website_reader import create_mcp_server

SAMPLE_ARTICLE_HTML = """
<html lang="en">
  <head>
    <title>My Article</title>
    <meta name="description" content="Short article description" />
    <meta property="og:site_name" content="Example" />
    <meta property="article:published_time" content="2024-05-01T10:00:00Z" />
    <meta name="author" content="Jane Doe" />
  </head>
  <body>
    <article>
      <h1>My Article</h1>
      <p>
        Clean readable article text with enough content for trafilatura to extract
        a meaningful article body from the page markup.
      </p>
      <p>
        A second paragraph adds more substance so extraction libraries can identify
        this as the main article content instead of boilerplate.
      </p>
    </article>
  </body>
</html>
"""

EMPTY_HTML = """
<html>
  <head><title>Empty</title></head>
  <body></body>
</html>
"""


def _article_response(url: str = "https://example.com/blog/my-article") -> FetchResponse:
    return FetchResponse(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=SAMPLE_ARTICLE_HTML,
    )


def test_normalize_whitespace():
    text = normalize_whitespace("Line   one\n\n\n\nLine two")

    assert text == "Line one\n\nLine two"


def test_extract_article_text_from_html():
    text, method = extract_article_text(SAMPLE_ARTICLE_HTML, url="https://example.com/article")

    assert text is not None
    assert "Clean readable article text" in text
    assert method == "trafilatura"


def test_build_summary_prompt_contains_text_and_title():
    prompt = build_summary_prompt(title="My Article", text="Body text", language="en", max_words=100)

    assert "My Article" in prompt
    assert "Body text" in prompt
    assert "100 words" in prompt


@pytest.mark.asyncio
async def test_tools_are_registered():
    mcp = create_mcp_server()
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {
        "fetch_url",
        "fetch_markdown",
        "extract_article",
        "extract_metadata",
        "summarize_article",
    } <= tool_names


@pytest.mark.asyncio
async def test_extract_article_content_success():
    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(return_value=_article_response()),
    ):
        result = await extract_article_content("https://example.com/blog/my-article")

    assert isinstance(result, ExtractArticleResult)
    assert result.error is None
    assert result.url == "https://example.com/blog/my-article"
    assert result.final_url == "https://example.com/blog/my-article"
    assert result.title == "My Article"
    assert result.description == "Short article description"
    assert result.author == "Jane Doe"
    assert result.published_date is not None
    assert result.text is not None
    assert "Clean readable article text" in result.text
    assert result.content_length == len(result.text)
    assert result.markdown is not None
    assert result.truncated is False
    assert result.extraction_method == "trafilatura"


@pytest.mark.asyncio
async def test_extract_article_can_skip_markdown():
    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(return_value=_article_response()),
    ):
        result = await extract_article_content(
            "https://example.com/blog/my-article",
            include_markdown=False,
        )

    assert result.markdown is None
    assert result.text is not None


@pytest.mark.asyncio
async def test_extract_article_rejects_invalid_url():
    result = await extract_article_content("not-a-url")

    assert result.error is not None
    assert result.text is None
    assert result.extraction_method == "trafilatura"


@pytest.mark.asyncio
async def test_extract_article_rejects_private_url():
    result = await extract_article_content("http://127.0.0.1/secret")

    assert result.error is not None
    assert "not allowed" in result.error.lower()
    assert result.text is None


@pytest.mark.asyncio
async def test_extract_article_handles_non_html_response():
    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(side_effect=FetchError("Unsupported content type: application/json")),
    ):
        result = await extract_article_content("https://example.com/data.json")

    assert result.error == "Unsupported content type: application/json"
    assert result.text is None


@pytest.mark.asyncio
async def test_extract_article_handles_empty_extraction():
    response = FetchResponse(
        url="https://example.com/empty",
        final_url="https://example.com/empty",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=EMPTY_HTML,
    )

    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(return_value=response),
    ):
        result = await extract_article_content("https://example.com/empty")

    assert result.error == EXTRACTION_FAILED_MESSAGE
    assert result.text is None


@pytest.mark.asyncio
async def test_extract_article_truncates_text():
    long_paragraph = "Word " * 5000
    html = f"""
    <html>
      <head><title>Long Article</title></head>
      <body>
        <article>
          <h1>Long Article</h1>
          <p>{long_paragraph}</p>
        </article>
      </body>
    </html>
    """
    response = FetchResponse(
        url="https://example.com/long",
        final_url="https://example.com/long",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=html,
    )

    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(return_value=response),
    ):
        result = await extract_article_content("https://example.com/long", max_chars=500)

    assert result.text is not None
    assert result.truncated is True
    assert result.content_length == len(result.text)
    assert len(result.text) <= 501


@pytest.mark.asyncio
async def test_extract_article_can_skip_metadata():
    with patch(
        "app.services.article_extractor.fetch_url_content",
        AsyncMock(return_value=_article_response()),
    ):
        result = await extract_article_content(
            "https://example.com/blog/my-article",
            include_metadata=False,
        )

    assert result.error is None
    assert result.title is None
    assert result.description is None
    assert result.text is not None
