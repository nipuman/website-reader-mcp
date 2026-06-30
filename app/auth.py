from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import Settings, get_settings


def extract_api_key(request: Request, settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()

    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()

    api_key = request.headers.get("X-API-Key")
    if api_key and api_key.strip():
        return api_key.strip()

    return None


def is_valid_api_key(request: Request, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    provided = extract_api_key(request, settings)
    if not provided:
        return False
    return provided == settings.mcp_api_key


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Protect MCP routes with a static API key."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/mcp" or request.url.path.startswith("/mcp/"):
            if not is_valid_api_key(request):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
