"""Tests for src/shopify_publisher.py (mocked HTTP)."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.config import Config
from src.shopify_publisher import (
    publish_digest_draft,
    get_blog_id,
    default_digest_title,
    ShopifyPublishError,
    SHOPIFY_API_VERSION,
)


@pytest.fixture
def shopify_env(monkeypatch):
    monkeypatch.setattr(Config, 'SHOPIFY_STORE_DOMAIN', 'test-store.myshopify.com')
    monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', 'shpat_testtoken')
    monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '')


@pytest.fixture
def digest_file(tmp_path):
    path = tmp_path / "2026-06-29-digest.html"
    path.write_text("<p>Digest body</p>", encoding='utf-8')
    return path


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestCredentials:
    def test_missing_token_clear_error(self, monkeypatch, digest_file):
        monkeypatch.setattr(Config, 'SHOPIFY_STORE_DOMAIN', 'test.myshopify.com')
        monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', '')

        with pytest.raises(ShopifyPublishError) as exc:
            publish_digest_draft(html_path=digest_file)
        assert 'SHOPIFY_ADMIN_TOKEN' in str(exc.value)

    def test_placeholder_token_rejected(self, monkeypatch, digest_file):
        monkeypatch.setattr(Config, 'SHOPIFY_STORE_DOMAIN', 'test.myshopify.com')
        monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', 'your_shopify_admin_token_here')

        with pytest.raises(ShopifyPublishError):
            publish_digest_draft(html_path=digest_file)

    def test_missing_domain_clear_error(self, monkeypatch, digest_file):
        monkeypatch.setattr(Config, 'SHOPIFY_STORE_DOMAIN', '')
        monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', 'shpat_x')

        with pytest.raises(ShopifyPublishError) as exc:
            publish_digest_draft(html_path=digest_file)
        assert 'SHOPIFY_STORE_DOMAIN' in str(exc.value)


class TestBlogId:
    def test_configured_blog_id_used(self, shopify_env, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '12345')
        assert get_blog_id('d', 't') == 12345

    def test_non_numeric_blog_id_rejected(self, shopify_env, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', 'not-a-number')
        with pytest.raises(ShopifyPublishError):
            get_blog_id('d', 't')

    @patch('src.shopify_publisher.requests.get')
    def test_first_blog_fetched_when_unset(self, mock_get, shopify_env):
        mock_get.return_value = _mock_response(
            {'blogs': [{'id': 777, 'title': 'News'}, {'id': 888, 'title': 'Other'}]}
        )
        blog_id = get_blog_id('test-store.myshopify.com', 'shpat_x')
        assert blog_id == 777
        url = mock_get.call_args[0][0]
        assert f'/admin/api/{SHOPIFY_API_VERSION}/blogs.json' in url

    @patch('src.shopify_publisher.requests.get')
    def test_no_blogs_raises(self, mock_get, shopify_env):
        mock_get.return_value = _mock_response({'blogs': []})
        with pytest.raises(ShopifyPublishError):
            get_blog_id('test-store.myshopify.com', 'shpat_x')


class TestPublishDraft:
    @patch('src.shopify_publisher.requests.post')
    def test_always_publishes_as_draft(self, mock_post, shopify_env, digest_file, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '111')
        mock_post.return_value = _mock_response(
            {'article': {'id': 42, 'title': 'Test'}}
        )

        article = publish_digest_draft(html_path=digest_file, title='Test')

        assert article['id'] == 42
        payload = mock_post.call_args[1]['json']
        assert payload['article']['published'] is False
        assert payload['article']['body_html'] == '<p>Digest body</p>'
        headers = mock_post.call_args[1]['headers']
        assert headers['X-Shopify-Access-Token'] == 'shpat_testtoken'
        url = mock_post.call_args[0][0]
        assert f'/admin/api/{SHOPIFY_API_VERSION}/blogs/111/articles.json' in url

    def test_missing_digest_file_raises(self, shopify_env, tmp_path):
        with pytest.raises(ShopifyPublishError):
            publish_digest_draft(html_path=tmp_path / "nope.html")

    @patch('src.shopify_publisher.find_latest_digest')
    def test_no_digest_found_clear_error(self, mock_find, shopify_env):
        mock_find.return_value = None
        with pytest.raises(ShopifyPublishError) as exc:
            publish_digest_draft()
        assert 'digest' in str(exc.value).lower()

    def test_default_title_pattern(self):
        title = default_digest_title(datetime(2026, 7, 6))
        assert title == "This Week in Mobile Gaming — July 6, 2026"
