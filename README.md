# Website Reader MCP

A small production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with Python and FastAPI. It exposes **Website Reader** tools over **Streamable HTTP** so an AI chat backend can fetch public webpages and receive cleaned, readable text.

## What it does

- Runs as a FastAPI app locally with uvicorn over HTTPS
- Deploys to Vercel as a Python serverless app (HTTPS provided by Vercel)
- Exposes MCP at `/mcp` (Streamable HTTP transport)
- Protects the MCP endpoint with a static API key
- Provides the `fetch_url` tool to fetch a public page and return structured metadata plus cleaned text
- Provides the `extract_article` tool to extract higher quality article content with rich metadata

## Tools: `fetch_url` vs `extract_article`

| Tool | Best for | Output |
| --- | --- | --- |
| `fetch_url` | Raw/simple fetch when you also need HTTP status, final URL, and content type | Cleaned page text plus basic title/description from HTML |
| `extract_article` | Summaries, blog posts, news, docs, and long-form pages | Article-focused text extracted with `trafilatura`, plus author, date, site name, language, and related metadata |

Use `extract_article` when you want the main readable article body. Use `fetch_url` when you need fetch diagnostics or a simpler HTML-to-text pass.

## Local setup

Requirements: Python 3.11+ and OpenSSL (for local dev certs)

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

HOST=0.0.0.0
PORT=8001
DEV_HTTPS=true
SSL_CERTFILE=certs/localhost.pem
SSL_KEYFILE=certs/localhost-key.pem
```

The real `.env` file is gitignored and should not be committed.

## Create local HTTPS certs

Local development uses self-signed TLS certs. Generate them once:

```bash
chmod +x scripts/dev.sh scripts/generate_dev_certs.sh
./scripts/generate_dev_certs.sh
```

This creates:

```text
certs/localhost.pem
certs/localhost-key.pem
```

These files are gitignored and are for local dev only.

You do not need to run this manually if you use `./scripts/dev.sh` — it auto-generates missing certs on first start.

### Optional: trusted local certs with mkcert

If you prefer browser- and client-trusted local certs instead of self-signed ones:

```bash
brew install mkcert
mkcert -install
mkdir -p certs
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1
```

Then use `./scripts/dev.sh` as usual.

## Run locally

```bash
./scripts/dev.sh
```

This starts uvicorn with reload on:

```text
https://localhost:8001
```

Useful overrides:

```bash
# HTTP instead of HTTPS
DEV_HTTPS=false ./scripts/dev.sh

# Bind only to localhost
HOST=127.0.0.1 ./scripts/dev.sh
```

## Health check

Self-signed certs require `-k` with curl:

```bash
curl -k https://localhost:8001/health
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
https://localhost:8001/mcp
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
curl -k -sS -X POST "https://localhost:8001/mcp/" \
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
curl -k -sS -X POST "https://localhost:8001/mcp/" \
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
curl -k -sS -X POST "https://localhost:8001/mcp/" \
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

### Call `extract_article`

```bash
curl -k -sS -X POST "https://localhost:8001/mcp/" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "extract_article",
      "arguments": {
        "url": "https://example.com/blog/my-article",
        "max_chars": 12000,
        "include_metadata": true
      }
    }
  }'
```

Example structured output:

```json
{
  "url": "https://example.com/blog/my-article",
  "title": "My Article",
  "author": null,
  "date": null,
  "description": "Short article description",
  "site_name": "Example",
  "language": "en",
  "text": "Clean readable article text...",
  "text_length": 8452,
  "truncated": false,
  "extraction_method": "trafilatura"
}
```

If extraction fails, the tool returns a structured error instead of crashing:

```json
{
  "url": "https://example.com/article",
  "error": "Could not extract readable article content from this page.",
  "text": null,
  "extraction_method": "trafilatura"
}
```

You can also connect with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) using Streamable HTTP transport, the HTTPS URL above, and the same API key. You may need to accept the self-signed certificate in your client.

## Tests

```bash
pytest
```

## Vercel deployment

1. Push this repository to GitHub.
2. Import the project in Vercel.
3. Set environment variables in the Vercel dashboard (at minimum `MCP_API_KEY`).
4. Deploy.

The included `vercel.json` routes all requests to `app/main.py`, which exports the ASGI `app` object required by `@vercel/python`. Vercel terminates HTTPS for you in production; the local cert files are not used there.

After deployment, your MCP endpoint will be:

```text
https://<your-project>.vercel.app/mcp
```

Use the same API key headers as in local development.

## Security notes and limitations

- The MCP endpoint is protected by a single static API key. Rotate the key if it is exposed.
- Local HTTPS uses self-signed certificates. Do not reuse them outside local development.
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
    extractor.py       HTML to readable text (BeautifulSoup, used by fetch_url)
    article_extractor.py  Article extraction with trafilatura
scripts/
  generate_dev_certs.sh  Create local self-signed TLS certs
  dev.sh                 Run uvicorn with HTTPS locally
tests/
  test_fetcher.py
  test_extractor.py
  test_extract_article.py
```

## Next steps

Possible follow-ups:

- add `fetch_markdown`
- add domain allowlist or blocklist
- add caching
- add rate limiting
- add logging and request IDs
- add an MCP client inside the existing AI Chat backend
- add tools for `search_web` and `read_url`
- validate DNS-resolved IPs before fetching (stronger SSRF protection)
