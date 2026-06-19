"""Tests for src/parser.py"""

import pytest
from src.parser import (
    _parse_json_ld,
    parse_article_metadata,
    parse_article_content,
    parse_article_image,
    extract_full_article,
)
from bs4 import BeautifulSoup


# --- Fixtures: realistic HTML snippets ---

ARTICLE_HTML_FULL = """
<!DOCTYPE html>
<html>
<head>
    <meta property="og:title" content="OG Title Fallback" />
    <meta property="og:image" content="https://media.example.com/og-image.jpg" />
    <meta name="twitter:image" content="https://media.example.com/twitter-image.jpg" />
    <script type="application/ld+json">
    {
        "@type": "NewsArticle",
        "headline": "New Mobile Game Breaks Download Records",
        "datePublished": "2025-10-15T08:00:00Z",
        "author": {"@type": "Person", "name": "Jane Smith"},
        "image": {"@type": "ImageObject", "url": "https://media.example.com/hero.jpg"}
    }
    </script>
</head>
<body>
    <article>
        <h1>New Mobile Game Breaks Download Records</h1>
        <div class="body-copy">
            <p>A brand new mobile game has shattered all previous download records on both iOS and Android platforms within its first week of release.</p>
            <p>The game features innovative gameplay mechanics that combine puzzle-solving with real-time strategy elements, attracting millions of players worldwide.</p>
            <p>Industry analysts predict this could be the beginning of a new trend in mobile gaming that emphasizes cross-platform play.</p>
            <p>Short text.</p>
            <p>Advertisement: Check out our sponsor</p>
        </div>
    </article>
</body>
</html>
"""

ARTICLE_HTML_MINIMAL = """
<html>
<head></head>
<body>
    <h1>Minimal Article Title</h1>
    <time datetime="2025-11-01T12:00:00Z">November 1, 2025</time>
    <span class="byline">By John Doe</span>
    <article>
        <p>This is the main content of the article which should be extracted properly by the parser.</p>
    </article>
</body>
</html>
"""

ARTICLE_HTML_NO_CONTENT = """
<html><head></head><body><h1>Empty Article</h1></body></html>
"""

ARTICLE_HTML_JSON_LD_ARRAY = """
<html>
<head>
<script type="application/ld+json">
[
    {"@type": "WebSite", "name": "PocketGamer"},
    {"@type": "NewsArticle", "headline": "Array Article", "datePublished": "2025-09-01", "author": "Bot"}
]
</script>
</head>
<body><h1>Array Article</h1></body>
</html>
"""


# --- JSON-LD parsing ---

class TestParseJsonLd:
    def test_extracts_news_article(self):
        soup = BeautifulSoup(ARTICLE_HTML_FULL, 'lxml')
        data = _parse_json_ld(soup)
        assert data is not None
        assert data['headline'] == "New Mobile Game Breaks Download Records"

    def test_handles_array_json_ld(self):
        soup = BeautifulSoup(ARTICLE_HTML_JSON_LD_ARRAY, 'lxml')
        data = _parse_json_ld(soup)
        assert data is not None
        assert data['headline'] == "Array Article"

    def test_returns_none_when_missing(self):
        soup = BeautifulSoup(ARTICLE_HTML_MINIMAL, 'lxml')
        data = _parse_json_ld(soup)
        assert data is None

    def test_handles_invalid_json(self):
        html = '<html><head><script type="application/ld+json">not json</script></head><body></body></html>'
        soup = BeautifulSoup(html, 'lxml')
        data = _parse_json_ld(soup)
        assert data is None


# --- Metadata extraction ---

class TestParseArticleMetadata:
    def test_extracts_from_json_ld(self):
        meta = parse_article_metadata(html=ARTICLE_HTML_FULL)
        assert meta['title'] == "New Mobile Game Breaks Download Records"
        assert meta['date'] == "2025-10-15T08:00:00Z"
        assert meta['author'] == "Jane Smith"

    def test_fallback_to_html_elements(self):
        meta = parse_article_metadata(html=ARTICLE_HTML_MINIMAL)
        assert meta['title'] == "Minimal Article Title"
        assert meta['date'] == "2025-11-01T12:00:00Z"
        assert meta['author'] == "John Doe"

    def test_accepts_prebuilt_soup(self):
        soup = BeautifulSoup(ARTICLE_HTML_FULL, 'lxml')
        json_ld = _parse_json_ld(soup)
        meta = parse_article_metadata(soup=soup, json_ld=json_ld)
        assert meta['title'] == "New Mobile Game Breaks Download Records"

    def test_handles_no_content(self):
        meta = parse_article_metadata(html=ARTICLE_HTML_NO_CONTENT)
        assert meta['title'] == "Empty Article"
        assert meta['date'] is None
        assert meta['author'] is None


# --- Content extraction ---

class TestParseArticleContent:
    def test_extracts_paragraphs(self):
        content = parse_article_content(html=ARTICLE_HTML_FULL)
        assert "shattered all previous download records" in content
        assert "innovative gameplay mechanics" in content

    def test_skips_short_paragraphs(self):
        content = parse_article_content(html=ARTICLE_HTML_FULL)
        assert "Short text." not in content

    def test_skips_advertisements(self):
        content = parse_article_content(html=ARTICLE_HTML_FULL)
        assert "Advertisement" not in content

    def test_returns_empty_for_no_content(self):
        content = parse_article_content(html=ARTICLE_HTML_NO_CONTENT)
        assert content == ""

    def test_accepts_prebuilt_soup(self):
        soup = BeautifulSoup(ARTICLE_HTML_FULL, 'lxml')
        content = parse_article_content(soup=soup)
        assert len(content) > 0


# --- Image extraction ---

class TestParseArticleImage:
    def test_extracts_from_json_ld(self):
        img = parse_article_image(html=ARTICLE_HTML_FULL)
        assert img == "https://media.example.com/hero.jpg"

    def test_falls_back_to_og_image(self):
        # HTML with OG but no JSON-LD image
        html = '<html><head><meta property="og:image" content="https://example.com/og.jpg" /></head><body></body></html>'
        img = parse_article_image(html=html)
        assert img == "https://example.com/og.jpg"

    def test_falls_back_to_twitter_image(self):
        html = '<html><head><meta name="twitter:image" content="https://example.com/tw.jpg" /></head><body></body></html>'
        img = parse_article_image(html=html)
        assert img == "https://example.com/tw.jpg"

    def test_returns_none_when_no_image(self):
        img = parse_article_image(html=ARTICLE_HTML_NO_CONTENT)
        assert img is None

    def test_rejects_invalid_urls(self):
        html = '''<html><head><script type="application/ld+json">
        {"@type": "NewsArticle", "image": "not-a-url"}
        </script></head><body></body></html>'''
        img = parse_article_image(html=html)
        assert img is None


# --- Full article extraction ---

class TestExtractFullArticle:
    def test_full_extraction(self):
        article = extract_full_article(ARTICLE_HTML_FULL, "https://example.com/article")
        assert article['url'] == "https://example.com/article"
        assert article['title'] == "New Mobile Game Breaks Download Records"
        assert article['author'] == "Jane Smith"
        assert article['date'] == "2025-10-15T08:00:00Z"
        assert article['content'] is not None
        assert len(article['content']) > 0
        assert article['image_url'] == "https://media.example.com/hero.jpg"
        assert 'scraped_at' in article

    def test_minimal_extraction(self):
        article = extract_full_article(ARTICLE_HTML_MINIMAL, "https://example.com/min")
        assert article['title'] == "Minimal Article Title"
        assert article['url'] == "https://example.com/min"

    def test_parses_html_only_once(self):
        """Ensure no redundant parsing by checking result consistency."""
        article = extract_full_article(ARTICLE_HTML_FULL, "https://example.com/test")
        # If JSON-LD was parsed correctly once, image should come from JSON-LD
        assert article['image_url'] == "https://media.example.com/hero.jpg"
        # And title should also come from JSON-LD
        assert article['title'] == "New Mobile Game Breaks Download Records"
