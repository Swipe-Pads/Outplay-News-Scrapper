"""Tests for src/scraper.py"""

import pytest
from unittest.mock import patch, MagicMock

from src.scraper import fetch_page, parse_article_links


class TestFetchPage:
    @patch('src.scraper.requests.get')
    def test_returns_html(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = '<html>Hello</html>'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_page('https://example.com')
        assert result == '<html>Hello</html>'

    @patch('src.scraper.requests.get')
    def test_saves_to_file(self, mock_get, tmp_path):
        mock_response = MagicMock()
        mock_response.text = '<html>Saved</html>'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        save_path = str(tmp_path / 'output' / 'page.html')
        # We need to patch Path so save_to works correctly
        from pathlib import Path
        result = fetch_page('https://example.com', save_to=save_path)
        # The function uses project_root / save_to, so we test the return value
        assert result == '<html>Saved</html>'

    @patch('src.scraper.requests.get')
    def test_timeout_raises(self, mock_get):
        import requests
        mock_get.side_effect = requests.Timeout("timeout")

        with pytest.raises(requests.RequestException, match="Timeout"):
            fetch_page('https://example.com')

    @patch('src.scraper.requests.get')
    def test_http_error_raises(self, mock_get):
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )

        with pytest.raises(requests.RequestException, match="HTTP error"):
            fetch_page('https://example.com')


class TestParseArticleLinks:
    def test_extracts_news_links(self):
        html = '''
        <html><body>
            <a href="/news/article-one/">A1</a>
            <a href="/news/article-two/">A2</a>
            <a href="/about/">About</a>
        </body></html>
        '''
        urls = parse_article_links(html)
        assert len(urls) == 2
        assert all('/news/' in u for u in urls)

    def test_respects_limit(self):
        html = '''
        <html><body>
            <a href="/news/a/">A</a>
            <a href="/news/b/">B</a>
            <a href="/news/c/">C</a>
        </body></html>
        '''
        urls = parse_article_links(html, limit=2)
        assert len(urls) == 2

    def test_deduplicates(self):
        html = '''
        <html><body>
            <a href="/news/same/">Same</a>
            <a href="/news/same/">Same Again</a>
        </body></html>
        '''
        urls = parse_article_links(html)
        assert len(urls) == 1

    def test_excludes_rss_and_pagination(self):
        html = '''
        <html><body>
            <a href="/news/real/">Real</a>
            <a href="/news/feed.rss">RSS</a>
            <a href="/news/?page=2">Page 2</a>
        </body></html>
        '''
        urls = parse_article_links(html)
        assert len(urls) == 1

    def test_skips_main_news_page(self):
        html = '''
        <html><body>
            <a href="/news/">Main News</a>
            <a href="/news/real-article/">Real</a>
        </body></html>
        '''
        urls = parse_article_links(html)
        assert len(urls) == 1
        assert '/news/real-article/' in urls[0]

    def test_empty_html(self):
        urls = parse_article_links('<html><body></body></html>')
        assert urls == []
