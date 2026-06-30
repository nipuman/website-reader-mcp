import pytest

from app.services.fetcher import URLValidationError, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "https://LOCALHOST/test",
        "http://127.0.0.1/",
        "https://127.0.0.2/secret",
        "http://127.0.0.1:8000",
        "http://192.168.0.1/",
        "https://192.168.1.10/page",
        "http://10.0.0.5/page",
        "https://10.255.255.255/",
        "http://172.31.255.255/",
        "https://172.16.0.1/page",
        "https://[::1]/",
        "http://[::1]/page",
        "http://169.254.1.1/",
        "https://169.254.169.254/latest/meta-data",
        "ftp://example.com/file",
        "not-a-url",
        "",
    ],
)
def test_validate_url_rejects_unsafe_or_invalid_urls(url: str):
    with pytest.raises(URLValidationError):
        validate_url(url)


def test_validate_url_accepts_public_http_and_https():
    http = validate_url("http://example.com")
    https = validate_url("https://example.org/path")

    assert http.scheme == "http"
    assert https.scheme == "https"
    assert https.hostname == "example.org"
