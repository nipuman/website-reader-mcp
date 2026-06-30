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


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
