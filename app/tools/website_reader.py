from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.config import get_settings
from app.schemas import FetchUrlResult
from app.services.extractor import extract_readable_content, truncate_text
from app.services.fetcher import FetchError, fetch_url_content

FETCH_URL_DESCRIPTION = (
    "Fetch a public webpage URL and return cleaned readable text, title, final URL, "
    "status code and basic metadata. Use this when the user wants to read, summarize "
    "or inspect a webpage."
)


def create_mcp_server() -> FastMCP:
    settings = get_settings()

    mcp = FastMCP(
        name=settings.service_name,
        instructions=(
            "Tools for fetching public webpages and returning cleaned readable text "
            "for summarization and inspection."
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

    return mcp
