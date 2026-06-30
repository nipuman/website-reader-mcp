from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from app.auth import ApiKeyMiddleware
from app.config import get_settings
from app.schemas import HealthResponse
from app.tools.website_reader import create_mcp_server

load_dotenv()

settings = get_settings()
mcp_server = create_mcp_server()
mcp_asgi_app = mcp_server.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title=settings.service_name,
    lifespan=lifespan,
)

app.add_middleware(ApiKeyMiddleware)
app.mount("/mcp", mcp_asgi_app)


@app.get("/")
async def root() -> HealthResponse:
    return HealthResponse(service=settings.service_name)


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(service=settings.service_name)
