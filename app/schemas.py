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


class ExtractArticleResult(BaseModel):
    url: str
    title: str | None = None
    author: str | None = None
    date: str | None = None
    description: str | None = None
    site_name: str | None = None
    language: str | None = None
    text: str | None = None
    text_length: int | None = None
    truncated: bool = False
    extraction_method: str = "trafilatura"
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
