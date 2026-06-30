from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mcp_api_key: str = Field(alias="MCP_API_KEY")
    app_env: str = Field(default="local", alias="APP_ENV")
    request_timeout_seconds: float = Field(default=12.0, alias="REQUEST_TIMEOUT_SECONDS")
    max_response_chars: int = Field(default=12000, alias="MAX_RESPONSE_CHARS")
    max_html_bytes: int = Field(default=2_000_000, alias="MAX_HTML_BYTES")
    allowed_schemes: str = Field(default="https,http", alias="ALLOWED_SCHEMES")

    user_agent: str = "WebsiteReaderMCP/0.1"
    max_redirects: int = 5
    service_name: str = "website-reader-mcp"

    @property
    def allowed_scheme_set(self) -> set[str]:
        return {scheme.strip().lower() for scheme in self.allowed_schemes.split(",") if scheme.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
