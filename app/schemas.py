from pydantic import BaseModel, Field


class FetchUrlResult(BaseModel):
    url: str
    final_url: str
    status_code: int
    content_type: str
    title: str | None = None
    description: str | None = None
    text: str
    truncated: bool = False
    char_count: int = Field(description="Length of the returned text field")


class FetchMarkdownResult(BaseModel):
    url: str
    final_url: str | None = None
    title: str | None = None
    markdown: str | None = None
    content_length: int = Field(default=0, description="Length of the returned markdown field")
    truncated: bool = False
    extraction_method: str = "trafilatura"
    error: str | None = None


class ExtractArticleResult(BaseModel):
    url: str
    final_url: str | None = None
    title: str | None = None
    author: str | None = None
    published_date: str | None = None
    description: str | None = None
    site_name: str | None = None
    language: str | None = None
    text: str | None = None
    markdown: str | None = None
    content_length: int = Field(default=0, description="Length of the returned text field")
    truncated: bool = False
    extraction_method: str = "trafilatura"
    error: str | None = None


class ExtractMetadataResult(BaseModel):
    url: str
    final_url: str | None = None
    title: str | None = None
    description: str | None = None
    author: str | None = None
    published_date: str | None = None
    site_name: str | None = None
    language: str | None = None
    image: str | None = None
    canonical_url: str | None = None
    error: str | None = None


class SummarizeArticleResult(BaseModel):
    url: str
    final_url: str | None = None
    title: str | None = None
    author: str | None = None
    published_date: str | None = None
    description: str | None = None
    text: str | None = None
    content_length: int = Field(default=0, description="Length of the returned text field")
    truncated: bool = False
    summary_prompt: str | None = None
    extraction_method: str = "trafilatura"
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
