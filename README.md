# Website Reader MCP

A small production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with Python and FastAPI. It exposes a **Website Reader** tool over **Streamable HTTP** so an AI chat backend can fetch public webpages and receive cleaned, readable text.

## What it does

- Runs as a FastAPI app locally with uvicorn
- Deploys to Vercel as a Python serverless app
- Exposes MCP at `/mcp` (Streamable HTTP transport)
- Protects the MCP endpoint with a static API key
- Provides the `fetch_url` tool to fetch a public page and return structured metadata plus cleaned text

## Local setup

Requirements: Python 3.11+

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set a real value for `MCP_API_KEY`.

## Environment variables

Copy `.env.example` to `.env`:

```env
MCP_API_KEY=change-me
APP_ENV=local
REQUEST_TIMEOUT_SECONDS=12
MAX_RESPONSE_CHARS=12000
MAX_HTML_BYTES=2000000
ALLOWED_SCHEMES=https,http
```

The real `.env` file is gitignored and should not be committed.

## Run locally

```bash
uvicorn app.main:app --reload --port 8001
```

## Health check

```bash
curl http://127.0.0.1:8001/health
```

Example response:

```json
{
  "status": "ok",
  "service": "website-reader-mcp"
}
```

## MCP endpoint

The MCP Streamable HTTP endpoint is:

```text
http://127.0.0.1:8001/mcp
```

Authentication is required. Use either header:

```http
Authorization: Bearer <MCP_API_KEY>
```

or:

```http
X-API-Key: <MCP_API_KEY>
```

### Quick MCP test with curl

Initialize a session (stateless mode):

```bash
curl -sS -X POST "http://127.0.0.1:8001/mcp" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "curl-test", "version": "0.1"}
    }
  }'
```

List tools:

```bash
curl -sS -X POST "http://127.0.0.1:8001/mcp" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

Call `fetch_url`:

```bash
curl -sS -X POST "http://127.0.0.1:8001/mcp" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "fetch_url",
      "arguments": {"url": "https://example.com"}
    }
  }'
```

Replace `change-me` with your configured `MCP_API_KEY`.

You can also connect with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) using Streamable HTTP transport and the same URL and API key.

## Tests

```bash
pytest
```

## Vercel deployment

1. Push this repository to GitHub.
2. Import the project in Vercel.
3. Set environment variables in the Vercel dashboard (at minimum `MCP_API_KEY`).
4. Deploy.

The included `vercel.json` routes all requests to `app/main.py`, which exports the ASGI `app` object required by `@vercel/python`.

After deployment, your MCP endpoint will be:

```text
https://<your-project>.vercel.app/mcp
```

Use the same API key headers as in local development.

## Security notes and limitations

- The MCP endpoint is protected by a single static API key. Rotate the key if it is exposed.
- SSRF protection blocks localhost, common internal hostnames, and private/link-local/multicast IP literals before fetching.
- DNS resolution is **not** yet validated against resolved private IPs (see TODO in `app/services/fetcher.py`).
- Only `http` and `https` URLs are allowed.
- Responses are capped by `MAX_HTML_BYTES` while downloading and `MAX_RESPONSE_CHARS` (or `max_chars`) for returned text.
- No JavaScript rendering: pages that require a browser will not be fully readable.
- No crawling, caching, or rate limiting yet.

## Project structure

```text
app/
  main.py              FastAPI app, health routes, MCP mount
  config.py            Environment settings
  auth.py              API key middleware
  schemas.py           Response models
  tools/
    website_reader.py  MCP tool registration
  services/
    fetcher.py         HTTP fetch + URL validation
    extractor.py       HTML to readable text
tests/
  test_fetcher.py
  test_extractor.py
```

## Next steps

Possible follow-ups:

- add `extract_article` with better readability extraction
- add `fetch_markdown`
- add domain allowlist or blocklist
- add caching
- add rate limiting
- add logging and request IDs
- add an MCP client inside the existing AI Chat backend
- add tools for `search_web` and `read_url`
- validate DNS-resolved IPs before fetching (stronger SSRF protection)
