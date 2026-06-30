from unittest.mock import AsyncMock, patch

import pytest

from app.schemas import ExtractArticleResult
from app.services.article_extractor import (
    EXTRACTION_FAILED_MESSAGE,
    extract_article_content,
    extract_article_text,
    extract_metadata_dict,
    normalize_whitespace,
)
from app.services.fetcher import FetchError, FetchResponse
from app.tools.website_reader import create_mcp_server

SAMPLE_ARTICLE_HTML = """
<html>
  <head>
    <title>My Article</title>
    <meta name="description" content="Short article description" />
    <meta property="og:site_name" content="Example" />
    <html lang="en">
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


def test_normalize_whitespace():
    text = normalize_whitespace("Line   one\n\n\n\nLine two")

    assert text == "Line one\n\nLine two"


def test_extract_article_text_from_html():
    text, method = extract_article_text(SAMPLE_ARTICLE_HTML, url="https://example.com/article")

    assert text is not None
    assert "Clean readable article text" in text
    assert method == "trafilatura"


def test_extract_metadata_dict():
    metadata = extract_metadata_dict(SAMPLE_ARTICLE_HTML, url="https://example.com/article")

    assert metadata["title"] == "My Article"
    assert metadata["description"] == "Short article description"


@pytest.mark.asyncio
async def test_extract_article_tool_is_registered():
    mcp = create_mcp_server()
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "extract_article" in tool_names
    assert "fetch_url" in tool_names


@pytest.mark.asyncio
async def test_extract_article_content_success():
    response = FetchResponse(
        url="https://example.com/blog/my-article",
        final_url="https://example.com/blog/my-article",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=SAMPLE_ARTICLE_HTML,
    )

    with patch("app.services.article_extractor.fetch_url_content", AsyncMock(return_value=response)):
        result = await extract_article_content("https://example.com/blog/my-article")

    assert isinstance(result, ExtractArticleResult)
    assert result.error is None
    assert result.url == "https://example.com/blog/my-article"
    assert result.title == "My Article"
    assert result.description == "Short article description"
    assert result.text is not None
    assert "Clean readable article text" in result.text
    assert result.text_length == len(result.text)
    assert result.truncated is False
    assert result.extraction_method == "trafilatura"


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

    with patch("app.services.article_extractor.fetch_url_content", AsyncMock(return_value=response)):
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

    with patch("app.services.article_extractor.fetch_url_content", AsyncMock(return_value=response)):
        result = await extract_article_content("https://example.com/long", max_chars=500)

    assert result.text is not None
    assert result.truncated is True
    assert result.text_length == len(result.text)
    assert len(result.text) <= 501


@pytest.mark.asyncio
async def test_extract_article_can_skip_metadata():
    response = FetchResponse(
        url="https://example.com/blog/my-article",
        final_url="https://example.com/blog/my-article",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=SAMPLE_ARTICLE_HTML,
    )

    with patch("app.services.article_extractor.fetch_url_content", AsyncMock(return_value=response)):
        result = await extract_article_content(
            "https://example.com/blog/my-article",
            include_metadata=False,
        )

    assert result.error is None
    assert result.title is None
    assert result.description is None
    assert result.text is not None
