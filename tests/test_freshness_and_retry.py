"""Tests for feed staleness guarding, fetch retry, and per-stage model routing.

These cover the 2026-07-29 changes:
  - dormant feeds must not leak year-old items into digests (TouchArcade case)
  - transient network failures get retried, 4xx does not
  - each pipeline stage talks to its configured model
  - entity extraction rides along with the summary and lands in the DB
"""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.config import Config
from src.scraper import fetch_page
from src.sources.website import WebsiteCollector, WebsiteConfig


def _rss(entries):
    """Build a minimal RSS document. entries = [(title, url, datetime|None)]"""
    items = []
    for title, url, when in entries:
        pub = f"<pubDate>{format_datetime(when)}</pubDate>" if when else ""
        items.append(
            f"<item><title>{title}</title><link>{url}</link>"
            f"<description>desc</description>{pub}</item>"
        )
    return f"<?xml version='1.0'?><rss><channel>{''.join(items)}</channel></rss>"


def _collector(**overrides):
    cfg = dict(
        name="testsite",
        listing_url="https://example.com/",
        base_url="https://example.com",
        link_pattern=r"/news/.+",
        rss_url="https://example.com/feed/",
    )
    cfg.update(overrides)
    return WebsiteCollector(WebsiteConfig(**cfg))


class TestFeedFreshness:
    def test_fresh_items_are_kept(self):
        now = datetime.now(timezone.utc)
        xml = _rss([
            ("Fresh", "https://example.com/news/fresh", now - timedelta(days=1)),
            ("Also fresh", "https://example.com/news/two", now - timedelta(days=3)),
        ])
        with patch('src.sources.website.fetch_page', return_value=xml):
            urls = _collector().discover(limit=20)
        assert len(urls) == 2

    def test_stale_items_are_dropped(self):
        now = datetime.now(timezone.utc)
        xml = _rss([
            ("Ancient", "https://example.com/news/old",
             now - timedelta(days=Config.MAX_ITEM_AGE_DAYS + 400)),
            ("Fresh", "https://example.com/news/new", now - timedelta(days=2)),
        ])
        with patch('src.sources.website.fetch_page', return_value=xml):
            urls = _collector().discover(limit=20)
        assert urls == ["https://example.com/news/new"]

    def test_fully_dormant_feed_falls_back_to_html_and_warns(self, caplog):
        """A feed with only stale items must not silently supply the pipeline."""
        now = datetime.now(timezone.utc)
        xml = _rss([
            ("Old 1", "https://example.com/news/a",
             now - timedelta(days=Config.MAX_ITEM_AGE_DAYS + 30)),
            ("Old 2", "https://example.com/news/b",
             now - timedelta(days=Config.MAX_ITEM_AGE_DAYS + 60)),
        ])
        # RSS yields nothing fresh -> discover() falls back to the HTML listing,
        # which we serve as an empty page.
        with patch('src.sources.website.fetch_page',
                   side_effect=[xml, "<html><body></body></html>"]):
            with caplog.at_level('WARNING'):
                urls = _collector().discover(limit=20)
        assert urls == []
        assert any('dormant' in r.message for r in caplog.records)

    def test_undated_items_are_kept(self):
        """No pubDate is not evidence of staleness — keep the item."""
        xml = _rss([("No date", "https://example.com/news/undated", None)])
        with patch('src.sources.website.fetch_page', return_value=xml):
            urls = _collector().discover(limit=20)
        assert urls == ["https://example.com/news/undated"]

    def test_exclude_patterns_apply_to_feed_urls(self):
        now = datetime.now(timezone.utc)
        xml = _rss([
            ("Tag page", "https://example.com/tag/rpg", now),
            ("Article", "https://example.com/news/real", now),
        ])
        collector = _collector(exclude_patterns=[r"/tag/"])
        with patch('src.sources.website.fetch_page', return_value=xml):
            urls = collector.discover(limit=20)
        assert urls == ["https://example.com/news/real"]


class TestFetchRetry:
    def test_retries_transient_5xx_then_succeeds(self):
        bad = MagicMock(status_code=503)
        good = MagicMock(status_code=200, text="<html>ok</html>")
        good.raise_for_status = MagicMock()

        with patch('src.scraper.requests.get', side_effect=[bad, good]) as mock_get:
            with patch('src.scraper.time.sleep'):
                html = fetch_page("https://example.com/x")

        assert html == "<html>ok</html>"
        assert mock_get.call_count == 2

    def test_does_not_retry_403(self):
        response = MagicMock(status_code=403)
        response.raise_for_status.side_effect = requests.HTTPError(response=response)

        with patch('src.scraper.requests.get', return_value=response) as mock_get:
            with pytest.raises(requests.RequestException, match="403"):
                fetch_page("https://example.com/blocked")

        assert mock_get.call_count == 1

    def test_gives_up_after_max_attempts(self):
        with patch('src.scraper.requests.get', side_effect=requests.Timeout()) as mock_get:
            with patch('src.scraper.time.sleep'):
                with pytest.raises(requests.RequestException, match="Timeout"):
                    fetch_page("https://example.com/slow", max_attempts=3)

        assert mock_get.call_count == 3


def _extraction_response(payload, in_tokens=100, out_tokens=50):
    block = MagicMock(type="text")
    block.text = payload
    response = MagicMock(content=[block])
    response.usage.input_tokens = in_tokens
    response.usage.output_tokens = out_tokens
    return response


class TestEntityExtraction:
    def test_returns_summary_and_entities(self):
        from src.summarizer import summarize_and_extract

        payload = (
            '{"summary": "· point one · point two", "games": ["Kingdom Rush 6"], '
            '"companies": ["Ironhide"], "platforms": ["iOS", "Android"], '
            '"event_type": "launch", "release_date": "2026-08-14", "price": null}'
        )
        client = MagicMock()
        client.messages.create.return_value = _extraction_response(payload)

        with patch('src.summarizer.get_client', return_value=client):
            with patch('src.summarizer.time.sleep'):
                summary, entities = summarize_and_extract("T", "C" * 100)

        assert summary == "· point one · point two"
        assert entities['games'] == ["Kingdom Rush 6"]
        assert entities['event_type'] == "launch"
        assert entities['release_date'] == "2026-08-14"
        # null price must not be stored as a key
        assert 'price' not in entities

    def test_uses_extract_model(self):
        from src.summarizer import summarize_and_extract

        client = MagicMock()
        client.messages.create.return_value = _extraction_response(
            '{"summary": "s", "event_type": "update"}'
        )
        with patch('src.summarizer.get_client', return_value=client):
            with patch('src.summarizer.time.sleep'):
                summarize_and_extract("T", "C")

        assert client.messages.create.call_args[1]['model'] == Config.MODEL_EXTRACT

    def test_falls_back_to_plain_summary_on_bad_json(self):
        from src.summarizer import summarize_and_extract

        client = MagicMock()
        client.messages.create.return_value = _extraction_response("not json at all")

        with patch('src.summarizer.get_client', return_value=client):
            with patch('src.summarizer.time.sleep'):
                with patch('src.summarizer.summarize_article',
                           return_value="plain summary") as mock_plain:
                    summary, entities = summarize_and_extract("T", "C")

        assert summary == "plain summary"
        assert entities == {}
        mock_plain.assert_called_once()


class TestEntityPersistence:
    def test_entities_round_trip_through_db(self, tmp_path):
        import json
        from src import database

        db_path = str(tmp_path / "t.db")
        database.init_db(db_path)
        database.insert_article({
            'url': 'https://example.com/a',
            'title': 'A',
            'content': 'body',
        }, db_path)

        database.update_article_summary(
            'https://example.com/a', 'sum', db_path,
            entities={'games': ['G'], 'event_type': 'launch'},
        )

        rows = database.get_recent_articles(days=7, db_path=db_path)
        stored = json.loads(rows[0]['entities'])
        assert stored['games'] == ['G']
        assert stored['event_type'] == 'launch'

    def test_summary_without_entities_leaves_column_null(self, tmp_path):
        from src import database

        db_path = str(tmp_path / "t.db")
        database.init_db(db_path)
        database.insert_article({
            'url': 'https://example.com/b', 'title': 'B', 'content': 'body',
        }, db_path)
        database.update_article_summary('https://example.com/b', 'sum', db_path)

        rows = database.get_recent_articles(days=7, db_path=db_path)
        assert rows[0]['entities'] is None


class TestCostTrackerPerModel:
    def test_prices_haiku_cheaper_than_sonnet(self):
        from src.summarizer import CostTracker

        haiku = CostTracker()
        haiku.add_usage(1_000_000, 0, model='claude-haiku-4-5-20251001')
        sonnet = CostTracker()
        sonnet.add_usage(1_000_000, 0, model='claude-sonnet-5')

        assert haiku.get_cost_estimate()['total_cost'] < \
            sonnet.get_cost_estimate()['total_cost']

    def test_tracks_models_separately(self):
        from src.summarizer import CostTracker

        tracker = CostTracker()
        tracker.add_usage(1000, 100, model='claude-haiku-4-5-20251001')
        tracker.add_usage(2000, 200, model='claude-sonnet-5')

        by_model = tracker.get_cost_estimate()['by_model']
        assert by_model['claude-haiku-4-5-20251001']['requests'] == 1
        assert by_model['claude-sonnet-5']['input_tokens'] == 2000
        assert tracker.total_requests == 2


class TestDigestFactTags:
    def test_facts_render_into_prompt_line(self):
        import json
        from src.digest import _format_facts

        tag = _format_facts({'entities': json.dumps({
            'event_type': 'launch',
            'release_date': '2026-08-14',
            'platforms': ['iOS', 'Android'],
        })})
        assert 'launch' in tag
        assert 'out 2026-08-14' in tag
        assert 'iOS, Android' in tag

    def test_missing_or_broken_entities_render_empty(self):
        from src.digest import _format_facts

        assert _format_facts({}) == ''
        assert _format_facts({'entities': 'not json'}) == ''
        assert _format_facts({'entities': '[]'}) == ''

    def test_release_date_before_article_is_dropped(self):
        """Observed live: Haiku stamped 2024-09-05 on a 2026 article."""
        import json
        from src.digest import _format_facts

        tag = _format_facts({
            'date': '2026-07-29T10:40:00+01:00',
            'entities': json.dumps({
                'event_type': 'event',
                'release_date': '2024-09-05',
            }),
        })
        assert 'event' in tag
        assert '2024' not in tag

    def test_future_release_date_is_kept(self):
        import json
        from src.digest import _format_facts

        tag = _format_facts({
            'date': '2026-07-29T10:40:00+01:00',
            'entities': json.dumps({'release_date': '2026-09-05'}),
        })
        assert 'out 2026-09-05' in tag

    def test_vague_release_date_passes_through(self):
        import json
        from src.digest import _format_facts

        tag = _format_facts({
            'date': '2026-07-29',
            'entities': json.dumps({'release_date': '2026 Q4'}),
        })
        assert '2026 Q4' in tag
