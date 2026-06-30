import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import Settings, get_settings

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
}

SUPPORTED_CONTENT_PREFIXES = ("text/html", "text/plain", "application/xhtml+xml")


class URLValidationError(ValueError):
    """Raised when a URL fails validation or SSRF checks."""


class FetchError(Exception):
    """Raised when a page cannot be fetched."""


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    scheme: str
    hostname: str


@dataclass(frozen=True)
class FetchResponse:
    url: str
    final_url: str
    status_code: int
    content_type: str
    body: str


def _normalize_hostname(hostname: str) -> str:
    return hostname.strip().lower().rstrip(".")


def _is_blocked_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if address.is_loopback:
        return True
    if address.is_private:
        return True
    if address.is_link_local:
        return True
    if address.is_multicast:
        return True
    if address.is_reserved:
        return True
    if address.is_unspecified:
        return True

    if isinstance(address, ipaddress.IPv4Address):
        if address in ipaddress.ip_network("0.0.0.0/8"):
            return True
        if address in ipaddress.ip_network("169.254.0.0/16"):
            return True
        if address in ipaddress.ip_network("224.0.0.0/4"):
            return True

    if isinstance(address, ipaddress.IPv6Address):
        if address in ipaddress.ip_network("fc00::/7"):
            return True
        if address in ipaddress.ip_network("fe80::/10"):
            return True

    return False


def _is_ip_literal(hostname: str) -> bool:
    return _try_parse_ip(hostname) is not None


def _try_parse_ip(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    host = hostname
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]

    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def validate_url(url: str, settings: Settings | None = None) -> ValidatedURL:
    """Validate a URL and reject unsafe targets before fetching.

    TODO: Resolve hostnames via DNS and reject if any resolved IP is private.
    """
    settings = settings or get_settings()
    cleaned = url.strip()

    if not cleaned:
        raise URLValidationError("URL is required.")

    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()

    if scheme not in settings.allowed_scheme_set:
        allowed = ", ".join(sorted(settings.allowed_scheme_set))
        raise URLValidationError(f"Only {allowed} URLs are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must include a hostname.")

    normalized_host = _normalize_hostname(hostname)
    if normalized_host in BLOCKED_HOSTNAMES:
        raise URLValidationError("Localhost and internal hostnames are not allowed.")

    if _is_ip_literal(normalized_host):
        ip_address = _try_parse_ip(normalized_host)
        if ip_address is None:
            raise URLValidationError("URL contains an invalid IP address.")

        if _is_blocked_ip(ip_address):
            raise URLValidationError("Private, loopback, and internal IP addresses are not allowed.")

    if not parsed.netloc:
        raise URLValidationError("Malformed URL.")

    return ValidatedURL(url=cleaned, scheme=scheme, hostname=normalized_host)


async def fetch_url_content(url: str, settings: Settings | None = None) -> FetchResponse:
    settings = settings or get_settings()

    try:
        validated = validate_url(url, settings)
    except URLValidationError as exc:
        raise FetchError(str(exc)) from exc

    headers = {"User-Agent": settings.user_agent}

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=settings.max_redirects,
            timeout=settings.request_timeout_seconds,
            headers=headers,
        ) as client:
            async with client.stream("GET", validated.url) as response:
                content_type = response.headers.get("content-type", "application/octet-stream")
                media_type = content_type.split(";", 1)[0].strip().lower()

                if not media_type.startswith(SUPPORTED_CONTENT_PREFIXES):
                    raise FetchError(
                        f"Unsupported content type: {content_type}. "
                        "Only HTML and plain text responses are supported."
                    )

                chunks: list[bytes] = []
                total_bytes = 0

                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > settings.max_html_bytes:
                        raise FetchError(
                            f"Response exceeded the maximum size of {settings.max_html_bytes} bytes."
                        )
                    chunks.append(chunk)

                body_bytes = b"".join(chunks)

                try:
                    body = body_bytes.decode(response.encoding or "utf-8")
                except UnicodeDecodeError:
                    body = body_bytes.decode("utf-8", errors="replace")

                return FetchResponse(
                    url=validated.url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    body=body,
                )
    except FetchError:
        raise
    except httpx.TooManyRedirects as exc:
        raise FetchError("Too many redirects while fetching the URL.") from exc
    except httpx.TimeoutException as exc:
        raise FetchError(
            f"Request timed out after {settings.request_timeout_seconds} seconds."
        ) from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"Failed to fetch URL: {exc}") from exc
