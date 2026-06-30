from app.services.extractor import extract_readable_content, truncate_text


def test_extracts_body_text_from_simple_html():
    html = """
    <html>
      <body>
        <p>Hello world.</p>
        <p>Second paragraph.</p>
      </body>
    </html>
    """

    result = extract_readable_content(html)

    assert "Hello world." in result.text
    assert "Second paragraph." in result.text


def test_extracts_title():
    html = """
    <html>
      <head><title>Example Title</title></head>
      <body><p>Body text</p></body>
    </html>
    """

    result = extract_readable_content(html)

    assert result.title == "Example Title"


def test_extracts_meta_description():
    html = """
    <html>
      <head>
        <meta name="description" content="A short summary of the page." />
      </head>
      <body><p>Body text</p></body>
    </html>
    """

    result = extract_readable_content(html)

    assert result.description == "A short summary of the page."


def test_normalizes_whitespace():
    html = """
    <html>
      <body>
        <p>Line   one</p>
        <p>Line two</p>
      </body>
    </html>
    """

    result = extract_readable_content(html)

    assert "  " not in result.text
    assert "Line one" in result.text
    assert "Line two" in result.text


def test_prefers_main_content():
    html = """
    <html>
      <body>
        <nav>Skip me</nav>
        <main><p>Main content only.</p></main>
      </body>
    </html>
    """

    result = extract_readable_content(html)

    assert "Main content only." in result.text
    assert "Skip me" not in result.text


def test_truncate_text():
    text = "abcdefghij"
    truncated, was_truncated = truncate_text(text, 5)

    assert was_truncated is True
    assert truncated.startswith("abcde")
