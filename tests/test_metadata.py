from unittest.mock import AsyncMock, patch

import pytest

from app.services.fetcher import FetchError, FetchResponse
from app.services.metadata_extractor import extract_page_metadata, get_page_metadata

RICH_HTML = """
<html lang="de">
  <head>
    <title>Fallback Title</title>
    <link rel="canonical" href="https://example.com/canonical" />
    <meta property="og:title" content="OG Title" />
    <meta property="og:description" content="OG description" />
    <meta property="og:site_name" content="Example Site" />
    <meta property="og:image" content="/images/cover.png" />
    <meta property="article:published_time" content="2024-03-15T08:30:00Z" />
    <meta name="author" content="Jane Doe" />
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      "headline": "JSON-LD Headline",
      "author": {"@type": "Person", "name": "John Smith"},
      "datePublished": "2024-03-14T00:00:00Z",
      "image": ["https://cdn.example.com/a.jpg"]
    }
    </script>
  </head>
  <body><p>Body</p></body>
</html>
"""

SPARSE_HTML = """
<html>
  <head><title>Only A Title</title></head>
  <body><p>Some text</p></body>
</html>
"""


def _response(body: str, url: str = "https://example.com/page") -> FetchResponse:
    return FetchResponse(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
    )


def test_extract_page_metadata_prefers_open_graph():
    metadata = extract_page_metadata(RICH_HTML, url="https://example.com/page")

    assert metadata["title"] == "OG Title"
    assert metadata["description"] == "OG description"
    assert metadata["site_name"] == "Example Site"
    assert metadata["author"] == "Jane Doe"
    assert metadata["published_date"] == "2024-03-15T08:30:00Z"
    assert metadata["language"] == "de"
    assert metadata["canonical_url"] == "https://example.com/canonical"
    assert metadata["image"] == "https://example.com/images/cover.png"


def test_extract_page_metadata_uses_jsonld_when_missing():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@type": "Article", "headline": "LD Only", "author": "Solo Author"}
        </script>
      </head>
      <body></body>
    </html>
    """
    metadata = extract_page_metadata(html, url="https://example.com/x")

    assert metadata["title"] == "LD Only"
    assert metadata["author"] == "Solo Author"


def test_extract_page_metadata_sparse_page():
    metadata = extract_page_metadata(SPARSE_HTML, url="https://example.com/page")

    assert metadata["title"] == "Only A Title"
    assert metadata["author"] is None
    assert metadata["image"] is None


@pytest.mark.asyncio
async def test_get_page_metadata_success():
    with patch(
        "app.services.metadata_extractor.fetch_url_content",
        AsyncMock(return_value=_response(RICH_HTML)),
    ):
        result = await get_page_metadata("https://example.com/page")

    assert result.error is None
    assert result.url == "https://example.com/page"
    assert result.final_url == "https://example.com/page"
    assert result.title == "OG Title"
    assert result.canonical_url == "https://example.com/canonical"
    assert result.language == "de"


@pytest.mark.asyncio
async def test_get_page_metadata_rejects_invalid_url():
    result = await get_page_metadata("not-a-url")

    assert result.error is not None
    assert result.title is None


@pytest.mark.asyncio
async def test_get_page_metadata_handles_fetch_error():
    with patch(
        "app.services.metadata_extractor.fetch_url_content",
        AsyncMock(side_effect=FetchError("Unsupported content type: application/pdf")),
    ):
        result = await get_page_metadata("https://example.com/file.pdf")

    assert result.error == "Unsupported content type: application/pdf"
    assert result.title is None
