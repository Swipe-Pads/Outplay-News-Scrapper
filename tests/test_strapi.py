"""Tests for src/strapi.py"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from src.strapi import (
    StrapiClient,
    StrapiSyncError,
    StrapiConnectionError,
    StrapiAuthError,
    StrapiUploadError,
    map_article_to_strapi,
    sync,
    _guess_mime_type,
)
from src import database


# === Helpers ===

def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def _sample_article(**overrides):
    base = {
        'id': 1,
        'url': 'https://example.com/news/test',
        'title': 'Test Article',
        'date': '2025-01-01T00:00:00Z',
        'author': 'Alice',
        'summary': 'Summary here',
        'content': 'Full content here',
        'image_path': None,
        'source_type': 'website',
        'source_name': 'pocketgamer',
        'strapi_id': None,
    }
    base.update(overrides)
    return base


# === StrapiClient ===

class TestStrapiClient:
    @patch('src.strapi.Config')
    @patch('src.strapi.requests.Session')
    def test_health_check_ok(self, mock_session_cls, mock_config):
        mock_config.STRAPI_URL = 'http://localhost:1337'
        mock_config.STRAPI_API_TOKEN = 'test-token'
        mock_session = MagicMock()
        mock_session.request.return_value = _mock_response(200, {'data': []})
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='test-token'
        )
        assert client.health_check() is True

    @patch('src.strapi.requests.Session')
    def test_health_check_unreachable(self, mock_session_cls):
        import requests as req
        mock_session = MagicMock()
        mock_session.request.side_effect = req.exceptions.ConnectionError("refused")
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='test-token'
        )
        assert client.health_check() is False

    @patch('src.strapi.requests.Session')
    def test_find_article_found(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mock_response(200, {
            'data': [{'id': 1, 'documentId': 'abc', 'title': 'Found'}]
        })
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='test-token'
        )
        result = client.find_article_by_source_url('https://example.com/1')
        assert result is not None
        assert result['documentId'] == 'abc'

    @patch('src.strapi.requests.Session')
    def test_find_article_not_found(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mock_response(200, {'data': []})
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='test-token'
        )
        result = client.find_article_by_source_url('https://example.com/missing')
        assert result is None

    @patch('src.strapi.requests.Session')
    def test_create_article(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mock_response(200, {
            'data': {'id': 42, 'documentId': 'xyz', 'title': 'New'}
        })
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='test-token'
        )
        result = client.create_article({'title': 'New', 'sourceUrl': 'https://x.com'})
        assert result['id'] == 42
        assert result['documentId'] == 'xyz'

    @patch('src.strapi.requests.Session')
    def test_update_article(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mock_response(200, {
            'data': {'id': 42, 'documentId': 'xyz', 'title': 'Updated'}
        })
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='test-token'
        )
        result = client.update_article('xyz', {'title': 'Updated'})
        assert result['title'] == 'Updated'

    @patch('src.strapi.requests.Session')
    def test_auth_error_no_retry(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mock_response(401, text="Unauthorized")
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='bad-token'
        )
        with pytest.raises(StrapiAuthError):
            client.find_article_by_source_url('https://x.com')

        assert mock_session.request.call_count == 1

    @patch('src.strapi.requests.Session')
    def test_retry_on_5xx(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.side_effect = [
            _mock_response(502, text="Bad Gateway"),
            _mock_response(200, {'data': []}),
        ]
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='token',
            retry_delay=0.01, rate_limit=0,
        )
        result = client.find_article_by_source_url('https://x.com')
        assert result is None
        assert mock_session.request.call_count == 2

    @patch('src.strapi.requests.Session')
    def test_upload_image(self, mock_session_cls, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"fake image data")

        mock_session = MagicMock()
        mock_session.request.return_value = _mock_response(200)
        mock_session.request.return_value.json.return_value = [
            {'id': 99, 'url': 'https://r2.dev/test.jpg'}
        ]
        mock_session_cls.return_value = mock_session

        client = StrapiClient(
            base_url='http://localhost:1337', api_token='token',
            rate_limit=0,
        )
        media_id = client.upload_image(str(img_file))
        assert media_id == 99

    @patch('src.strapi.requests.Session')
    def test_upload_image_missing_file(self, mock_session_cls):
        mock_session_cls.return_value = MagicMock()
        client = StrapiClient(
            base_url='http://localhost:1337', api_token='token'
        )
        result = client.upload_image('/nonexistent/img.jpg')
        assert result is None

    @patch('src.strapi.Config')
    def test_no_token_raises(self, mock_config):
        mock_config.STRAPI_URL = 'http://localhost:1337'
        mock_config.STRAPI_API_TOKEN = ''
        with pytest.raises(StrapiAuthError, match="not configured"):
            StrapiClient(base_url='http://localhost:1337', api_token='')


# === Mapping ===

class TestMapArticle:
    def test_maps_all_fields(self):
        article = _sample_article()
        result = map_article_to_strapi(article, media_id=42)

        assert result['title'] == 'Test Article'
        assert result['sourceUrl'] == 'https://example.com/news/test'
        assert result['sourceType'] == 'website'
        assert result['sourceName'] == 'pocketgamer'
        assert result['coverImage'] == 42

    def test_maps_without_image(self):
        article = _sample_article()
        result = map_article_to_strapi(article)
        assert 'coverImage' not in result

    def test_maps_youtube_article(self):
        article = _sample_article(
            source_type='youtube', source_name='iFerg',
            url='https://youtube.com/watch?v=123'
        )
        result = map_article_to_strapi(article)
        assert result['sourceType'] == 'youtube'
        assert result['sourceName'] == 'iFerg'


# === Mime type ===

class TestGuessMimeType:
    def test_jpg(self):
        assert _guess_mime_type(Path("img.jpg")) == "image/jpeg"

    def test_png(self):
        assert _guess_mime_type(Path("img.png")) == "image/png"

    def test_unknown(self):
        assert _guess_mime_type(Path("file.xyz")) == "application/octet-stream"


# === Sync ===

class TestSync:
    @pytest.fixture(autouse=True)
    def fake_strapi_token(self, monkeypatch):
        """sync() requires STRAPI_API_TOKEN — fake it so tests don't need .env."""
        from src.config import Config
        monkeypatch.setattr(Config, 'STRAPI_API_TOKEN', 'test-token')

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = tmp_path / "test.db"
        database.init_db(str(db_path))
        return str(db_path)

    @patch('src.strapi.StrapiClient')
    def test_sync_creates_new_articles(self, mock_client_cls, temp_db):
        # Insert article
        database.insert_article({
            'url': 'https://example.com/new',
            'title': 'New Article',
            'content': 'Content',
            'source_type': 'website',
            'source_name': 'test',
        }, temp_db)

        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.find_article_by_source_url.return_value = None
        mock_client.create_article.return_value = {
            'id': 1, 'documentId': 'abc123'
        }
        mock_client_cls.return_value = mock_client

        stats = sync(batch_size=10, publish=False, db_path=temp_db)

        assert stats['created'] == 1
        assert stats['failed'] == 0
        mock_client.create_article.assert_called_once()

    @patch('src.strapi.StrapiClient')
    def test_sync_updates_existing(self, mock_client_cls, temp_db):
        database.insert_article({
            'url': 'https://example.com/existing',
            'title': 'Existing',
            'source_type': 'website',
            'source_name': 'test',
        }, temp_db)

        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.find_article_by_source_url.return_value = {
            'id': 5, 'documentId': 'existing-doc',
            'coverImage': None,
        }
        mock_client.update_article.return_value = {
            'id': 5, 'documentId': 'existing-doc'
        }
        mock_client_cls.return_value = mock_client

        stats = sync(batch_size=10, publish=False, db_path=temp_db)

        assert stats['updated'] == 1
        mock_client.update_article.assert_called_once()

    @patch('src.strapi.StrapiClient')
    def test_sync_handles_strapi_down(self, mock_client_cls, temp_db):
        database.insert_article({
            'url': 'https://example.com/down',
            'title': 'Down',
            'source_type': 'website',
            'source_name': 'test',
        }, temp_db)

        mock_client = MagicMock()
        mock_client.health_check.return_value = False
        mock_client_cls.return_value = mock_client

        stats = sync(batch_size=10, db_path=temp_db)

        assert stats['total'] == 0
        mock_client.create_article.assert_not_called()

    @patch('src.strapi.StrapiClient')
    def test_sync_continues_on_failure(self, mock_client_cls, temp_db):
        database.insert_article({
            'url': 'https://example.com/a', 'title': 'A',
            'source_type': 'website', 'source_name': 'test',
        }, temp_db)
        database.insert_article({
            'url': 'https://example.com/b', 'title': 'B',
            'source_type': 'website', 'source_name': 'test',
        }, temp_db)

        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.find_article_by_source_url.return_value = None
        mock_client.create_article.side_effect = [
            StrapiSyncError("First failed"),
            {'id': 2, 'documentId': 'doc2'},
        ]
        mock_client_cls.return_value = mock_client

        stats = sync(batch_size=10, publish=False, db_path=temp_db)

        assert stats['created'] == 1
        assert stats['failed'] == 1
        assert mock_client.create_article.call_count == 2

    @patch('src.strapi.Config')
    def test_sync_skips_without_token(self, mock_config, temp_db):
        mock_config.STRAPI_API_TOKEN = ''
        mock_config.STRAPI_PUBLISH = False
        mock_config.DATABASE_FULL_PATH = Path(temp_db)

        stats = sync(db_path=temp_db)
        assert stats['total'] == 0

    @patch('src.strapi.StrapiClient')
    def test_sync_publishes_when_requested(self, mock_client_cls, temp_db):
        database.insert_article({
            'url': 'https://example.com/pub',
            'title': 'Publish Me',
            'source_type': 'website',
            'source_name': 'test',
        }, temp_db)

        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.find_article_by_source_url.return_value = None
        mock_client.create_article.return_value = {
            'id': 10, 'documentId': 'pub-doc'
        }
        mock_client_cls.return_value = mock_client

        stats = sync(batch_size=10, publish=True, db_path=temp_db)

        assert stats['created'] == 1
        mock_client.publish_article.assert_called_once_with('pub-doc')


# === Scheduler integration ===

class TestStrapiSyncJob:
    @patch('src.scheduler.strapi_sync')
    def test_sync_job_calls_sync(self, mock_sync):
        from src.scheduler import strapi_sync_job
        mock_sync.return_value = {
            'total': 5, 'created': 3, 'updated': 1, 'failed': 1, 'skipped': 0
        }
        strapi_sync_job(batch_size=10, publish=False)
        mock_sync.assert_called_once()

    @patch('src.scheduler.strapi_sync')
    def test_sync_job_handles_exception(self, mock_sync):
        from src.scheduler import strapi_sync_job
        mock_sync.side_effect = RuntimeError("boom")
        strapi_sync_job()  # should not raise

    def test_scheduler_includes_strapi_job_when_token_set(self):
        from src.scheduler import create_scheduler
        with patch('src.scheduler.Config') as mock_config:
            mock_config.STRAPI_API_TOKEN = 'test-token'
            scheduler = create_scheduler(enable_strapi=True)
            job_ids = [j.id for j in scheduler.get_jobs()]
            assert 'strapi_sync_job' in job_ids

    def test_scheduler_excludes_strapi_job_without_token(self):
        from src.scheduler import create_scheduler
        with patch('src.scheduler.Config') as mock_config:
            mock_config.STRAPI_API_TOKEN = ''
            scheduler = create_scheduler(enable_strapi=True)
            job_ids = [j.id for j in scheduler.get_jobs()]
            assert 'strapi_sync_job' not in job_ids
