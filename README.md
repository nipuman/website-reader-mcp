# Website Reader MCP

A small production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with Python and FastAPI. It exposes **Website Reader** tools over **Streamable HTTP** so an AI chat backend can fetch public webpages and receive cleaned, readable text.

## What it does

- Runs as a FastAPI app locally with uvicorn over HTTPS
- Deploys to Vercel as a Python serverless app (HTTPS provided by Vercel)
- Exposes MCP at `/mcp` (Streamable HTTP transport)
- Protects the MCP endpoint with a static API key
- Provides a small content extraction pipeline: raw fetch, Markdown, article extraction, metadata and summary preparation

## Tools

The server exposes five MCP tools so the AI Chat backend can pick the right extraction layer for the task:

| Tool | Best for | Output |
| --- | --- | --- |
| `fetch_url` | Raw/simple fetch for debugging or fallback when you also need HTTP status, final URL and content type | Cleaned page text plus basic title/description from HTML |
| `fetch_markdown` | RAG ingestion and LLM context | Clean, LLM-friendly Markdown with headings, paragraphs, links, lists and code blocks; boilerplate removed |
| `extract_article` | Summaries, blog posts, news, docs and long-form pages | Main article text **and** Markdown, plus author, published date, description, site name and language |
| `extract_metadata` | Link previews and routing | Title, description, author, published date, site name, language, image and canonical URL (Open Graph, Twitter card, JSON-LD, meta tags) |
| `summarize_article` | Preparing an article summary without coupling the server to an LLM | Article text plus a ready-to-use `summary_prompt` the chat backend passes to its own model |

Markdown and article extraction are powered by [`trafilatura`](https://trafilatura.readthedocs.io/), with a lightweight BeautifulSoup fallback when trafilatura cannot find usable content. All tools return **structured error messages** instead of crashing on invalid URLs, timeouts, unsupported content types, empty pages or extraction failures.

### `summarize_article` and LLMs

`summarize_article` deliberately does **not** call OpenAI or any other model from inside the MCP server. It returns the extracted `text` together with a `summary_prompt` string. The AI Chat backend can send `summary_prompt` to its existing model pipeline to produce the actual summary. This keeps the MCP server provider-agnostic.

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

### Call `fetch_markdown`

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
      "name": "fetch_markdown",
      "arguments": {
        "url": "https://example.com/blog/my-article",
        "max_chars": 12000
      }
    }
  }'
```

Example structured output:

```json
{
  "url": "https://example.com/blog/my-article",
  "final_url": "https://example.com/blog/my-article",
  "title": "My Article",
  "markdown": "# My Article\n\nClean readable content...\n\n- point one\n- point two",
  "content_length": 842,
  "truncated": false,
  "extraction_method": "trafilatura",
  "error": null
}
```

### Call `extract_article`

```bash
curl -k -sS -X POST "https://localhost:8001/mcp/" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "extract_article",
      "arguments": {
        "url": "https://example.com/blog/my-article",
        "max_chars": 12000,
        "include_metadata": true,
        "include_markdown": true
      }
    }
  }'
```

Example structured output:

```json
{
  "url": "https://example.com/blog/my-article",
  "final_url": "https://example.com/blog/my-article",
  "title": "My Article",
  "author": "Jane Doe",
  "published_date": "2024-05-01T10:00:00Z",
  "description": "Short article description",
  "site_name": "Example",
  "language": "en",
  "text": "Clean readable article text...",
  "markdown": "# My Article\n\nClean readable article text...",
  "content_length": 8452,
  "truncated": false,
  "extraction_method": "trafilatura",
  "error": null
}
```

If extraction fails, the tool returns a structured error instead of crashing:

```json
{
  "url": "https://example.com/article",
  "final_url": "https://example.com/article",
  "error": "Could not extract readable article content from this page.",
  "text": null,
  "markdown": null,
  "extraction_method": "trafilatura"
}
```

### Call `extract_metadata`

```bash
curl -k -sS -X POST "https://localhost:8001/mcp/" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 6,
    "method": "tools/call",
    "params": {
      "name": "extract_metadata",
      "arguments": {"url": "https://example.com/blog/my-article"}
    }
  }'
```

Example structured output:

```json
{
  "url": "https://example.com/blog/my-article",
  "final_url": "https://example.com/blog/my-article",
  "title": "My Article",
  "description": "Short article description",
  "author": "Jane Doe",
  "published_date": "2024-05-01T10:00:00Z",
  "site_name": "Example",
  "language": "en",
  "image": "https://example.com/images/cover.png",
  "canonical_url": "https://example.com/blog/my-article",
  "error": null
}
```

### Call `summarize_article`

```bash
curl -k -sS -X POST "https://localhost:8001/mcp/" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 7,
    "method": "tools/call",
    "params": {
      "name": "summarize_article",
      "arguments": {
        "url": "https://example.com/blog/my-article",
        "max_chars": 12000,
        "max_words": 150
      }
    }
  }'
```

Example structured output:

```json
{
  "url": "https://example.com/blog/my-article",
  "final_url": "https://example.com/blog/my-article",
  "title": "My Article",
  "author": "Jane Doe",
  "published_date": "2024-05-01T10:00:00Z",
  "description": "Short article description",
  "text": "Clean readable article text...",
  "content_length": 8452,
  "truncated": false,
  "summary_prompt": "Summarize My Article in at most 150 words. Focus on the key points...\n\nArticle content:\nClean readable article text...",
  "extraction_method": "trafilatura",
  "error": null
}
```

The chat backend passes `summary_prompt` to its own LLM to generate the final summary.

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
    website_reader.py  MCP tool registration (all five tools)
  services/
    fetcher.py             HTTP fetch + URL validation (SSRF checks)
    extractor.py           HTML to readable text (BeautifulSoup, used by fetch_url)
    markdown_extractor.py  HTML to Markdown (trafilatura + BeautifulSoup fallback)
    metadata_extractor.py  Metadata (Open Graph, Twitter, JSON-LD, meta tags)
    article_extractor.py   Article extraction and summary prompt preparation
scripts/
  generate_dev_certs.sh  Create local self-signed TLS certs
  dev.sh                 Run uvicorn with HTTPS locally
tests/
  test_fetcher.py
  test_extractor.py
  test_extract_article.py
  test_markdown.py
  test_metadata.py
  test_summarize.py
```

## Next steps

Possible follow-ups:

- add domain allowlist or blocklist
- add caching
- add rate limiting
- add logging and request IDs
- add an MCP client inside the existing AI Chat backend
- add tools for `search_web` and `read_url`
- validate DNS-resolved IPs before fetching (stronger SSRF protection)
