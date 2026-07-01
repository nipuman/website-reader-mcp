from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.config import get_settings
from app.schemas import (
    ExtractArticleResult,
    ExtractMetadataResult,
    FetchMarkdownResult,
    FetchUrlResult,
    SummarizeArticleResult,
)
from app.services.article_extractor import (
    extract_article_content,
    prepare_article_summary,
)
from app.services.extractor import extract_readable_content, truncate_text
from app.services.fetcher import FetchError, fetch_url_content
from app.services.markdown_extractor import get_markdown
from app.services.metadata_extractor import get_page_metadata

FETCH_URL_DESCRIPTION = (
    "Fetch a public webpage URL and return cleaned readable text, title, final URL, "
    "status code and basic metadata. Use this for raw/debug fetches or as a fallback "
    "when the richer extraction tools do not return usable content."
)

FETCH_MARKDOWN_DESCRIPTION = (
    "Fetch a public webpage and convert it into clean, LLM-friendly Markdown with "
    "headings, paragraphs, lists, links and code blocks preserved. Boilerplate such "
    "as scripts, styles, navigation and cookie banners is removed. Best for RAG "
    "ingestion and providing page context to a model."
)

EXTRACT_ARTICLE_DESCRIPTION = (
    "Fetch a public webpage and extract the main readable article content with rich "
    "metadata (author, published date, description, site name, language) plus a "
    "Markdown rendering. Prefer this for news, blog posts and long-form pages."
)

EXTRACT_METADATA_DESCRIPTION = (
    "Fetch a public webpage and return only its metadata (title, description, author, "
    "published date, site name, language, image, canonical URL) using Open Graph, "
    "Twitter card, JSON-LD and standard meta tags. Best for link previews and routing."
)

SUMMARIZE_ARTICLE_DESCRIPTION = (
    "Fetch a public webpage, extract the main article and return the article text "
    "together with a ready-to-use `summary_prompt`. This tool does NOT call an LLM "
    "itself; the chat backend should pass `summary_prompt` to its own model."
)


def create_mcp_server() -> FastMCP:
    settings = get_settings()

    mcp = FastMCP(
        name=settings.service_name,
        instructions=(
            "Tools for fetching public webpages and turning them into clean text, "
            "Markdown, article content, metadata and summary prompts for LLMs."
        ),
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
    )

    @mcp.tool(
        name="fetch_url",
        description=FETCH_URL_DESCRIPTION,
        structured_output=True,
    )
    async def fetch_url(url: str, max_chars: int | None = None) -> FetchUrlResult:
        try:
            response = await fetch_url_content(url, settings)
        except FetchError as exc:
            raise ToolError(str(exc)) from exc

        content_type = response.content_type.lower()
        if "html" in content_type or "xhtml" in content_type:
            extracted = extract_readable_content(response.body)
            title = extracted.title
            description = extracted.description
            text = extracted.text
        else:
            title = None
            description = None
            text = response.body.strip()

        char_limit = max_chars if max_chars is not None else settings.max_response_chars
        text, truncated = truncate_text(text, char_limit)

        return FetchUrlResult(
            url=response.url,
            final_url=response.final_url,
            status_code=response.status_code,
            content_type=response.content_type,
            title=title,
            description=description,
            text=text,
            truncated=truncated,
            char_count=len(text),
        )

    @mcp.tool(
        name="fetch_markdown",
        description=FETCH_MARKDOWN_DESCRIPTION,
        structured_output=True,
    )
    async def fetch_markdown(url: str, max_chars: int | None = None) -> FetchMarkdownResult:
        return await get_markdown(url=url, max_chars=max_chars, settings=settings)

    @mcp.tool(
        name="extract_article",
        description=EXTRACT_ARTICLE_DESCRIPTION,
        structured_output=True,
    )
    async def extract_article(
        url: str,
        max_chars: int | None = 20000,
        include_metadata: bool = True,
        include_markdown: bool = True,
    ) -> ExtractArticleResult:
        return await extract_article_content(
            url=url,
            max_chars=max_chars,
            include_metadata=include_metadata,
            include_markdown=include_markdown,
            settings=settings,
        )

    @mcp.tool(
        name="extract_metadata",
        description=EXTRACT_METADATA_DESCRIPTION,
        structured_output=True,
    )
    async def extract_metadata(url: str) -> ExtractMetadataResult:
        return await get_page_metadata(url=url, settings=settings)

    @mcp.tool(
        name="summarize_article",
        description=SUMMARIZE_ARTICLE_DESCRIPTION,
        structured_output=True,
    )
    async def summarize_article(
        url: str,
        max_chars: int | None = 12000,
        max_words: int = 150,
    ) -> SummarizeArticleResult:
        return await prepare_article_summary(
            url=url,
            max_chars=max_chars,
            max_words=max_words,
            settings=settings,
        )

    return mcp
