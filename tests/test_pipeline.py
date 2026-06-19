"""Tests for src/pipeline.py"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src import database
from src.pipeline import (
    process_collected_item,
    scrape_all_sources,
    process_single_article,
    process_batch,
    get_article_urls_from_listing,
    summarize_unsummarized,
)
from src.image_downloader import ImageDownloadError
from src.sources.base import CollectedItem


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(str(db_path))
    return str(db_path)


# === process_collected_item ===

class TestProcessCollectedItem:
    def test_stores_new_item(self, temp_db):
        item = {
            'url': 'https://example.com/1',
            'title': 'Test Article',
            'content': 'Some content',
            'image_url': None,
            'date': '2025-01-01',
            'author': 'Alice',
            'source_type': 'website',
            'source_name': 'test',
            'content_id': None,
        }
        result = process_collected_item(item, summarize=False, db_path=temp_db)
        assert result is not None
        assert result['title'] == 'Test Article'
        assert result['id'] is not None

    def test_skips_existing(self, temp_db):
        item = {
            'url': 'https://example.com/dup',
            'title': 'Dup',
            'source_type': 'website',
            'source_name': 'test',
        }
        database.insert_article({'url': item['url'], 'title': 'Existing'}, temp_db)

        result = process_collected_item(item, summarize=False, db_path=temp_db)
        assert result is None

    @patch('src.pipeline.download_image')
    def test_handles_image_download_error(self, mock_dl, temp_db):
        mock_dl.side_effect = ImageDownloadError("fail")
        item = {
            'url': 'https://example.com/img-fail',
            'title': 'Img Fail',
            'image_url': 'https://example.com/bad.jpg',
            'source_type': 'website',
            'source_name': 'test',
        }
        result = process_collected_item(item, summarize=False, db_path=temp_db)
        assert result is not None
        assert result['image_path'] is None


# === scrape_all_sources ===

class TestScrapeAllSources:
    @patch('src.pipeline.scrape_all_sources.__module__', 'src.pipeline')
    @patch('src.sources.registry._sources', None)
    @patch('src.sources.registry._load_sources')
    def test_returns_stats(self, mock_load, temp_db):
        mock_collector = MagicMock()
        mock_collector.source_type = 'website'
        mock_collector.source_name = 'mock'
        mock_collector.discover.return_value = ['https://example.com/a']
        mock_collector.collect.return_value = CollectedItem(
            url='https://example.com/a',
            title='Mock Article',
            source_type='website',
            source_name='mock',
            content='Content',
        )
        mock_load.return_value = [mock_collector]

        # Reset the cached sources
        import src.sources.registry as reg
        reg._sources = None

        stats = scrape_all_sources(
            limit=5, summarize=False,
            db_path=temp_db, rate_limit=0,
        )

        assert stats['total'] >= 1
        assert stats['success'] >= 1
        reg._sources = None  # cleanup

    @patch('src.sources.registry._sources', None)
    @patch('src.sources.registry._load_sources')
    def test_empty_sources(self, mock_load, temp_db):
        mock_load.return_value = []
        import src.sources.registry as reg
        reg._sources = None

        stats = scrape_all_sources(
            source_type='nonexistent',
            limit=5, summarize=False,
            db_path=temp_db
        )
        assert stats['total'] == 0
        reg._sources = None


# === Legacy functions ===

class TestLegacyFunctions:
    @patch('src.pipeline.fetch_page')
    @patch('src.pipeline.extract_full_article')
    def test_process_single_article(self, mock_extract, mock_fetch, temp_db):
        mock_fetch.return_value = '<html></html>'
        mock_extract.return_value = {
            'url': 'https://example.com/single',
            'title': 'Test', 'content': 'Content',
            'date': '2025-01-01', 'author': 'Bob',
            'image_url': None,
        }

        result = process_single_article(
            'https://example.com/single',
            skip_existing=True, summarize=False,
            db_path=temp_db
        )
        assert result is not None
        assert result['title'] == 'Test'

    @patch('src.pipeline.fetch_page')
    @patch('src.pipeline.extract_full_article')
    def test_process_single_article_skips_existing(self, mock_extract, mock_fetch, temp_db):
        database.insert_article({
            'url': 'https://example.com/exists',
            'title': 'Existing'
        }, temp_db)

        result = process_single_article(
            'https://example.com/exists',
            skip_existing=True, summarize=False,
            db_path=temp_db
        )
        assert result is None
        mock_fetch.assert_not_called()

    @patch('src.pipeline.fetch_page')
    def test_get_article_urls_from_listing(self, mock_fetch):
        mock_fetch.return_value = '''
        <html><body>
            <a href="/news/article-1/">A1</a>
            <a href="/news/article-2/">A2</a>
        </body></html>
        '''
        urls = get_article_urls_from_listing(limit=10)
        assert len(urls) == 2

    @patch('src.pipeline.fetch_page')
    @patch('src.pipeline.extract_full_article')
    def test_process_batch(self, mock_extract, mock_fetch, temp_db):
        mock_fetch.return_value = '<html></html>'
        # extract_full_article needs to return title; url is set by process_single_article
        call_count = [0]
        urls = ['https://example.com/b1', 'https://example.com/b2']

        def side_effect(html, url):
            return {
                'url': url,
                'title': f'Batch {call_count[0]}', 'content': 'C',
                'image_url': None,
            }

        mock_extract.side_effect = side_effect

        stats = process_batch(
            urls,
            rate_limit=0, skip_existing=True,
            summarize=False, db_path=temp_db
        )
        assert stats['total'] == 2
        assert stats['success'] == 2
        assert stats['failed'] == 0
