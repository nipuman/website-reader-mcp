from unittest.mock import AsyncMock, patch

import pytest

from app.services.fetcher import FetchError, FetchResponse
from app.services.markdown_extractor import (
    MARKDOWN_FAILED_MESSAGE,
    _bs4_markdown,
    get_markdown,
    html_to_markdown,
)

SAMPLE_HTML = """
<html lang="en">
  <head>
    <title>Markdown Sample</title>
    <script>console.log('tracking');</script>
    <style>body { color: red; }</style>
  </head>
  <body>
    <nav>Home | About | Contact</nav>
    <main>
      <article>
        <h1>Main Heading</h1>
        <p>First paragraph with a <a href="https://example.com">link</a> and <strong>bold</strong> text.</p>
        <h2>Subsection</h2>
        <ul>
          <li>First item</li>
          <li>Second item</li>
        </ul>
        <pre><code>print("hello")</code></pre>
      </article>
    </main>
    <footer>Cookie banner and copyright noise.</footer>
  </body>
</html>
"""


def _html_response(url: str = "https://example.com/post") -> FetchResponse:
    return FetchResponse(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=SAMPLE_HTML,
    )


def test_html_to_markdown_keeps_structure():
    markdown, method = html_to_markdown(SAMPLE_HTML, url="https://example.com/post")

    assert markdown is not None
    assert "Main Heading" in markdown
    assert method in {"trafilatura", "beautifulsoup4"}
    assert "console.log" not in markdown
    assert "color: red" not in markdown


def test_bs4_markdown_fallback_structure():
    markdown = _bs4_markdown(SAMPLE_HTML)

    assert markdown is not None
    assert "# Main Heading" in markdown
    assert "## Subsection" in markdown
    assert "- First item" in markdown
    assert "[link](https://example.com)" in markdown
    assert "```" in markdown


@pytest.mark.asyncio
async def test_get_markdown_success():
    with patch(
        "app.services.markdown_extractor.fetch_url_content",
        AsyncMock(return_value=_html_response()),
    ):
        result = await get_markdown("https://example.com/post")

    assert result.error is None
    assert result.url == "https://example.com/post"
    assert result.final_url == "https://example.com/post"
    assert result.title in {"Markdown Sample", "Main Heading"}
    assert result.markdown is not None
    assert result.content_length == len(result.markdown)
    assert "Main Heading" in result.markdown


@pytest.mark.asyncio
async def test_get_markdown_truncates():
    with patch(
        "app.services.markdown_extractor.fetch_url_content",
        AsyncMock(return_value=_html_response()),
    ):
        result = await get_markdown("https://example.com/post", max_chars=20)

    assert result.markdown is not None
    assert result.truncated is True
    assert result.content_length == len(result.markdown)


@pytest.mark.asyncio
async def test_get_markdown_rejects_invalid_url():
    result = await get_markdown("not-a-url")

    assert result.error is not None
    assert result.markdown is None


@pytest.mark.asyncio
async def test_get_markdown_handles_fetch_error():
    with patch(
        "app.services.markdown_extractor.fetch_url_content",
        AsyncMock(side_effect=FetchError("Request timed out after 12 seconds.")),
    ):
        result = await get_markdown("https://example.com/slow")

    assert result.error == "Request timed out after 12 seconds."
    assert result.markdown is None


@pytest.mark.asyncio
async def test_get_markdown_handles_empty_page():
    response = FetchResponse(
        url="https://example.com/empty",
        final_url="https://example.com/empty",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body="<html><head><title>Empty</title></head><body></body></html>",
    )
    with patch(
        "app.services.markdown_extractor.fetch_url_content",
        AsyncMock(return_value=response),
    ):
        result = await get_markdown("https://example.com/empty")

    assert result.error == MARKDOWN_FAILED_MESSAGE
    assert result.markdown is None
