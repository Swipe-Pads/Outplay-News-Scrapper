"""Tests for src/shopify_publisher.py (mocked HTTP)."""

import base64
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.config import Config
from src.shopify_publisher import (
    publish_digest_draft,
    get_access_token,
    get_blog_id,
    default_digest_title,
    ShopifyPublishError,
    SHOPIFY_API_VERSION,
)


@pytest.fixture
def shopify_env(monkeypatch):
    """Client-credentials configuration (preferred auth path)."""
    monkeypatch.setattr(Config, 'SHOPIFY_STORE_DOMAIN', 'test-store.myshopify.com')
    monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_ID', 'client_id_123')
    monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_SECRET', 'client_secret_456')
    monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', '')
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


# === Access token (client credentials grant) ===

class TestAccessToken:
    @patch('src.shopify_publisher.requests.post')
    def test_client_credentials_exchange(self, mock_post, shopify_env):
        mock_post.return_value = _mock_response({'access_token': 'fresh_token_24h'})

        token = get_access_token('test-store.myshopify.com')

        assert token == 'fresh_token_24h'
        url = mock_post.call_args[0][0]
        assert url == 'https://test-store.myshopify.com/admin/oauth/access_token'
        payload = mock_post.call_args[1]['json']
        assert payload == {
            'client_id': 'client_id_123',
            'client_secret': 'client_secret_456',
            'grant_type': 'client_credentials',
        }

    @patch('src.shopify_publisher.requests.post')
    def test_exchange_without_token_in_response(self, mock_post, shopify_env):
        mock_post.return_value = _mock_response({})
        with pytest.raises(ShopifyPublishError) as exc:
            get_access_token('test-store.myshopify.com')
        assert 'access_token' in str(exc.value)

    def test_falls_back_to_static_admin_token(self, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_ID', '')
        monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_SECRET', '')
        monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', 'shpat_static')

        assert get_access_token('test-store.myshopify.com') == 'shpat_static'

    def test_no_credentials_clear_error(self, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_ID', '')
        monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_SECRET', '')
        monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', '')

        with pytest.raises(ShopifyPublishError) as exc:
            get_access_token('test-store.myshopify.com')
        message = str(exc.value)
        assert 'SHOPIFY_CLIENT_ID' in message
        assert 'SHOPIFY_ADMIN_TOKEN' in message

    def test_placeholder_credentials_rejected(self, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_ID', 'your_shopify_client_id_here')
        monkeypatch.setattr(Config, 'SHOPIFY_CLIENT_SECRET', 'your_shopify_client_secret_here')
        monkeypatch.setattr(Config, 'SHOPIFY_ADMIN_TOKEN', '')

        with pytest.raises(ShopifyPublishError):
            get_access_token('test-store.myshopify.com')


class TestDomain:
    def test_missing_domain_clear_error(self, monkeypatch, digest_file):
        monkeypatch.setattr(Config, 'SHOPIFY_STORE_DOMAIN', '')
        with pytest.raises(ShopifyPublishError) as exc:
            publish_digest_draft(html_path=digest_file)
        assert 'SHOPIFY_STORE_DOMAIN' in str(exc.value)


# === Blog id resolution ===

class TestBlogId:
    def test_configured_blog_id_used(self, shopify_env, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '126947590478')
        assert get_blog_id('d', 't') == 126947590478

    def test_non_numeric_blog_id_rejected(self, shopify_env, monkeypatch):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', 'not-a-number')
        with pytest.raises(ShopifyPublishError):
            get_blog_id('d', 't')

    @patch('src.shopify_publisher.requests.get')
    def test_first_blog_fetched_when_unset(self, mock_get, shopify_env):
        mock_get.return_value = _mock_response(
            {'blogs': [{'id': 777, 'title': 'News'}, {'id': 888, 'title': 'Other'}]}
        )
        blog_id = get_blog_id('test-store.myshopify.com', 'tok')
        assert blog_id == 777
        url = mock_get.call_args[0][0]
        assert f'/admin/api/{SHOPIFY_API_VERSION}/blogs.json' in url

    @patch('src.shopify_publisher.requests.get')
    def test_no_blogs_raises(self, mock_get, shopify_env):
        mock_get.return_value = _mock_response({'blogs': []})
        with pytest.raises(ShopifyPublishError):
            get_blog_id('test-store.myshopify.com', 'tok')


# === Publishing ===

class TestPublishDraft:
    @patch('src.shopify_publisher.compose_excerpt')
    @patch('src.shopify_publisher.get_access_token')
    @patch('src.shopify_publisher.requests.post')
    def test_always_publishes_as_draft_with_summary(
        self, mock_post, mock_token, mock_excerpt, shopify_env, digest_file, monkeypatch
    ):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '111')
        mock_token.return_value = 'fresh_token'
        mock_excerpt.return_value = 'Big story teaser. Your 5-minute catch-up. →'
        mock_post.return_value = _mock_response({'article': {'id': 42, 'title': 'Test'}})

        article = publish_digest_draft(
            html_path=digest_file, title='Test', attach_image=False
        )

        assert article['id'] == 42
        payload = mock_post.call_args[1]['json']
        assert payload['article']['published'] is False
        assert payload['article']['body_html'] == '<p>Digest body</p>'
        assert payload['article']['summary_html'] == (
            '<p>Big story teaser. Your 5-minute catch-up. →</p>'
        )
        assert 'image' not in payload['article']
        headers = mock_post.call_args[1]['headers']
        assert headers['X-Shopify-Access-Token'] == 'fresh_token'
        url = mock_post.call_args[0][0]
        assert f'/admin/api/{SHOPIFY_API_VERSION}/blogs/111/articles.json' in url

    @patch('src.shopify_publisher.compose_excerpt')
    @patch('src.shopify_publisher.get_access_token')
    @patch('src.shopify_publisher.requests.post')
    def test_fresh_token_exchanged_on_every_run(
        self, mock_post, mock_token, mock_excerpt, shopify_env, digest_file, monkeypatch
    ):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '111')
        mock_token.return_value = 'tok'
        mock_excerpt.return_value = 'Excerpt. Your 5-minute catch-up. →'
        mock_post.return_value = _mock_response({'article': {'id': 1}})

        publish_digest_draft(html_path=digest_file, title='T', attach_image=False)
        publish_digest_draft(html_path=digest_file, title='T', attach_image=False)

        assert mock_token.call_count == 2

    @patch('src.shopify_publisher.compose_excerpt')
    @patch('src.shopify_publisher.get_access_token')
    @patch('src.shopify_publisher.requests.post')
    def test_cover_image_attached_base64_with_alt(
        self, mock_post, mock_token, mock_excerpt, shopify_env, digest_file, monkeypatch
    ):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '111')
        mock_token.return_value = 'tok'
        mock_excerpt.return_value = 'Excerpt. Your 5-minute catch-up. →'
        mock_post.return_value = _mock_response({'article': {'id': 7}})

        # Matching cover PNG sitting next to the digest file
        cover_bytes = b'\x89PNG fake bytes'
        (digest_file.parent / '2026-06-29-cover.png').write_bytes(cover_bytes)

        publish_digest_draft(html_path=digest_file, title='My Title')

        payload = mock_post.call_args[1]['json']
        image = payload['article']['image']
        assert image['attachment'] == base64.b64encode(cover_bytes).decode('ascii')
        assert image['alt'] == 'My Title'
        assert image['filename'] == '2026-06-29-cover.png'

    @patch('src.shopify_publisher.compose_excerpt')
    @patch('src.shopify_publisher.get_access_token')
    @patch('src.shopify_publisher.requests.post')
    def test_publish_continues_when_cover_generation_fails(
        self, mock_post, mock_token, mock_excerpt, shopify_env, digest_file, monkeypatch
    ):
        monkeypatch.setattr(Config, 'SHOPIFY_BLOG_ID', '111')
        mock_token.return_value = 'tok'
        mock_excerpt.return_value = 'Excerpt. Your 5-minute catch-up. →'
        mock_post.return_value = _mock_response({'article': {'id': 9}})

        # No sibling cover; force generation failure
        with patch('src.image_generator.generate_cover_image', side_effect=RuntimeError('boom')):
            article = publish_digest_draft(html_path=digest_file, title='T')

        assert article['id'] == 9
        payload = mock_post.call_args[1]['json']
        assert 'image' not in payload['article']

    @patch('src.shopify_publisher.get_access_token')
    def test_missing_digest_file_raises(self, mock_token, shopify_env, tmp_path):
        mock_token.return_value = 'tok'
        with pytest.raises(ShopifyPublishError):
            publish_digest_draft(html_path=tmp_path / "nope.html")

    @patch('src.shopify_publisher.find_latest_digest')
    @patch('src.shopify_publisher.get_access_token')
    def test_no_digest_found_clear_error(self, mock_token, mock_find, shopify_env):
        mock_token.return_value = 'tok'
        mock_find.return_value = None
        with pytest.raises(ShopifyPublishError) as exc:
            publish_digest_draft()
        assert 'digest' in str(exc.value).lower()

    def test_default_title_pattern(self):
        title = default_digest_title(datetime(2026, 7, 6))
        assert title == "This Week in Mobile Gaming — July 6, 2026"
