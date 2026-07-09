"""Tests for multi-source system."""

import pytest
from unittest.mock import patch, MagicMock
from src.sources.base import BaseCollector, CollectedItem
from src.sources.registry import get_sources, get_source, list_sources, get_all_sources
from src.sources.website import WebsiteCollector, WebsiteConfig, WEBSITE_CONFIGS
from src import database


class TestCollectedItem:
    def test_to_dict(self):
        item = CollectedItem(
            url="https://example.com/1",
            title="Test",
            source_type="website",
            source_name="test",
            date="2025-01-01",
            author="Author",
            content="Content",
        )
        d = item.to_dict()
        assert d['url'] == "https://example.com/1"
        assert d['source_type'] == "website"
        assert d['source_name'] == "test"
        assert d['content_id'] is None


class TestRegistry:
    def test_list_sources_returns_all(self):
        sources = list_sources()
        # 5 websites + 12 YouTube channels + 3 subreddits
        assert len(sources) >= 20
        types = {s['type'] for s in sources}
        assert 'website' in types
        assert 'youtube' in types
        assert 'reddit' in types

    def test_get_sources_filter_by_type(self):
        websites = get_sources(source_type='website')
        assert all(s.source_type == 'website' for s in websites)
        assert len(websites) == 5

    def test_get_sources_filter_by_name(self):
        result = get_sources(source_name='pocketgamer')
        assert len(result) == 1
        assert result[0].source_name == 'pocketgamer'

    def test_get_source_single(self):
        s = get_source('pocketgamer')
        assert s is not None
        assert s.source_type == 'website'

    def test_get_source_nonexistent(self):
        s = get_source('nonexistent_source')
        assert s is None


class TestWebsiteConfigs:
    def test_all_configs_have_required_fields(self):
        for name, config in WEBSITE_CONFIGS.items():
            assert config.name == name
            assert config.listing_url.startswith('http')
            assert config.base_url.startswith('http')
            assert config.link_pattern

    def test_pocketgamer_config(self):
        config = WEBSITE_CONFIGS['pocketgamer']
        assert 'pocketgamer.com' in config.listing_url


class TestWebsiteCollector:
    def test_init(self):
        config = WEBSITE_CONFIGS['pocketgamer']
        collector = WebsiteCollector(config)
        assert collector.source_type == 'website'
        assert collector.source_name == 'pocketgamer'

    @patch('src.sources.website.fetch_page')
    def test_discover_parses_links(self, mock_fetch):
        mock_fetch.return_value = '''
        <html><body>
            <a href="/news/article-one/">Article One</a>
            <a href="/news/article-two/">Article Two</a>
            <a href="/about/">About</a>
        </body></html>
        '''
        config = WEBSITE_CONFIGS['pocketgamer']
        collector = WebsiteCollector(config)
        urls = collector.discover(limit=5)
        assert len(urls) == 2
        assert all('pocketgamer.com/news/' in u for u in urls)

    @patch('src.sources.website.extract_full_article')
    @patch('src.sources.website.fetch_page')
    def test_collect_returns_item(self, mock_fetch, mock_extract):
        mock_fetch.return_value = '<html></html>'
        mock_extract.return_value = {
            'title': 'Test Article', 'date': '2025-01-01',
            'author': 'Alice', 'content': 'Content', 'image_url': None
        }
        config = WEBSITE_CONFIGS['pocketgamer']
        collector = WebsiteCollector(config)
        item = collector.collect('https://pocketgamer.com/news/test/')
        assert item is not None
        assert item.title == 'Test Article'
        assert item.source_type == 'website'
        assert item.source_name == 'pocketgamer'


class TestDatabaseSourceFields:
    """Test that DB handles the new source columns."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = tmp_path / "test.db"
        database.init_db(str(db_path))
        return str(db_path)

    def test_insert_with_source_fields(self, temp_db):
        article = {
            "url": "https://youtube.com/watch?v=123",
            "title": "YouTube Video",
            "source_type": "youtube",
            "source_name": "iFerg",
            "content_id": "123",
        }
        article_id = database.insert_article(article, temp_db)
        assert article_id is not None

        fetched = database.get_article_by_url(article["url"], temp_db)
        assert fetched["source_type"] == "youtube"
        assert fetched["source_name"] == "iFerg"
        assert fetched["content_id"] == "123"

    def test_get_articles_by_source(self, temp_db):
        database.insert_article({
            "url": "https://a.com/1", "title": "A",
            "source_type": "website", "source_name": "pocketgamer"
        }, temp_db)
        database.insert_article({
            "url": "https://b.com/2", "title": "B",
            "source_type": "youtube", "source_name": "iFerg"
        }, temp_db)
        database.insert_article({
            "url": "https://c.com/3", "title": "C",
            "source_type": "reddit", "source_name": "AndroidGaming"
        }, temp_db)

        websites = database.get_articles_by_source(source_type="website", db_path=temp_db)
        assert len(websites) == 1

        youtube = database.get_articles_by_source(source_type="youtube", db_path=temp_db)
        assert len(youtube) == 1

        all_articles = database.get_articles_by_source(db_path=temp_db)
        assert len(all_articles) == 3

    def test_default_source_values(self, temp_db):
        database.insert_article({
            "url": "https://d.com/4", "title": "D",
        }, temp_db)
        fetched = database.get_article_by_url("https://d.com/4", temp_db)
        assert fetched["source_type"] == "website"
        assert fetched["source_name"] == "unknown"
