"""Tests for src/sources/newsletter.py (KV inbox -> Claude extraction)"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.sources import newsletter
from src.sources.newsletter import (
    NewsletterCollector,
    _email_body_html,
    _key_age_days,
    _resolve_url,
    _sender_config,
    _strip_tracking_params,
    get_newsletter_collectors,
)


@pytest.fixture(autouse=True)
def fresh_inbox_cache():
    newsletter._reset_inbox_cache()
    yield
    newsletter._reset_inbox_cache()


def _iso(days_ago=0.0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _mime(html_body, subject="GI Daily | Test", sender="noreply@gamesindustry.biz"):
    return (
        f"From: Newsletter <{sender}>\r\n"
        f"To: digest@news.outplay.game\r\n"
        f"Subject: {subject}\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"{html_body}\r\n"
    ).encode("utf-8")


class TestSenderConfig:
    def test_known_sender_matches(self):
        cfg = _sender_config("\"GamesIndustry.biz\" <noreply@gamesindustry.biz>")
        assert cfg and cfg["name"] == "gamesindustry.biz"

    def test_sponsored_gi_mail_is_blocked(self):
        assert _sender_config("GI <contact@gamesindustry.biz>") is None

    def test_unknown_sender_is_none(self):
        assert _sender_config("spam@example.com") is None

    def test_substack_sender_maps_to_mobilegamer(self):
        cfg = _sender_config("mobilegamer.biz <mobilegamerbiz@substack.com>")
        assert cfg and cfg["name"] == "mobilegamer.biz"


class TestKeyAge:
    def test_recent_key(self):
        age = _key_age_days(f"nl:{_iso(2)}:abcd1234")
        assert age is not None and 1.9 < age < 2.1

    def test_garbage_key(self):
        assert _key_age_days("nl:not-a-date:xyz") is None
        assert _key_age_days("weird") is None


class TestEmailBody:
    def test_extracts_html_and_drops_styles(self):
        raw = _mime("<style>body{color:red}</style><p>Hello <a href='x'>link</a></p>")
        body = _email_body_html(raw)
        assert "Hello" in body and "color:red" not in body

    def test_empty_message(self):
        raw = (b"From: a@b.c\r\nTo: d@e.f\r\nSubject: hi\r\n\r\n")
        assert _email_body_html(raw).strip() in ("", "\r\n")


class TestLinkHygiene:
    def test_strips_utm_params(self):
        url = _strip_tracking_params(
            "https://example.com/article?id=5&utm_source=newsletter&utm_medium=email")
        assert url == "https://example.com/article?id=5"

    @patch("src.sources.newsletter.requests.get")
    def test_resolves_substack_redirect(self, mock_get):
        mock_get.return_value.url = "https://mobilegamer.biz/story?utm_source=substack"
        resolved = _resolve_url("https://substack.com/redirect/abc123")
        assert resolved == "https://mobilegamer.biz/story"

    @patch("src.sources.newsletter.requests.get")
    def test_direct_url_not_fetched(self, mock_get):
        resolved = _resolve_url("https://www.gamesindustry.biz/some-article")
        mock_get.assert_not_called()
        assert resolved == "https://www.gamesindustry.biz/some-article"

    @patch("src.sources.newsletter.requests.get", side_effect=OSError("boom"))
    def test_resolution_failure_returns_original(self, mock_get):
        resolved = _resolve_url("https://link.example.com/t/xyz?utm_source=nl")
        assert resolved == "https://link.example.com/t/xyz"


def _kv_env(monkeypatch):
    monkeypatch.setattr(newsletter.Config, "CF_ACCOUNT_ID", "acct")
    monkeypatch.setattr(newsletter.Config, "NEWSLETTER_KV_NAMESPACE_ID", "ns")
    monkeypatch.setattr(newsletter.Config, "CF_KV_API_TOKEN", "token")
    monkeypatch.setattr(newsletter.Config, "API_RATE_LIMIT_SECONDS", 0)


class TestLoadInbox:
    def test_unconfigured_returns_empty(self, monkeypatch):
        monkeypatch.setattr(newsletter.Config, "NEWSLETTER_KV_NAMESPACE_ID", "")
        assert newsletter._load_inbox() == {}

    @patch("src.sources.newsletter._extract_items")
    @patch("src.sources.newsletter._kv_get_value")
    @patch("src.sources.newsletter._kv_list_keys")
    def test_filters_old_blocked_and_unknown(self, mock_list, mock_get, mock_extract,
                                             monkeypatch):
        _kv_env(monkeypatch)
        mock_list.return_value = [
            # in window, known sender -> processed
            {"name": f"nl:{_iso(1)}:aaaa",
             "metadata": {"from": "noreply@gamesindustry.biz", "subject": "GI Daily"}},
            # sponsored -> skipped
            {"name": f"nl:{_iso(1)}:bbbb",
             "metadata": {"from": "contact@gamesindustry.biz", "subject": "Sponsored"}},
            # unknown sender -> skipped
            {"name": f"nl:{_iso(1)}:cccc",
             "metadata": {"from": "spam@example.com", "subject": "Buy stuff"}},
            # too old -> skipped
            {"name": f"nl:{_iso(30)}:dddd",
             "metadata": {"from": "noreply@gamesindustry.biz", "subject": "Old issue"}},
        ]
        mock_get.return_value = _mime("<p><a href='https://x.com/a'>A</a></p>")
        mock_extract.return_value = [
            {"url": "https://www.gamesindustry.biz/a", "title": "A", "summary": "s"}]

        inbox = newsletter._load_inbox()

        assert mock_get.call_count == 1
        assert list(inbox.keys()) == ["gamesindustry.biz"]
        assert inbox["gamesindustry.biz"][0]["email_subject"] == "GI Daily"

    @patch("src.sources.newsletter._extract_items", side_effect=RuntimeError("api down"))
    @patch("src.sources.newsletter._kv_get_value")
    @patch("src.sources.newsletter._kv_list_keys")
    def test_one_bad_email_does_not_kill_run(self, mock_list, mock_get, mock_extract,
                                             monkeypatch):
        _kv_env(monkeypatch)
        mock_list.return_value = [
            {"name": f"nl:{_iso(1)}:aaaa",
             "metadata": {"from": "noreply@gamesindustry.biz", "subject": "GI Daily"}},
        ]
        mock_get.return_value = _mime("<p>content</p>")
        assert newsletter._load_inbox() == {}


class TestNewsletterCollector:
    def _prime_inbox(self, items):
        newsletter._inbox = {"gamesindustry.biz": items}

    def test_init(self):
        c = NewsletterCollector("naavik")
        assert c.source_type == "newsletter"
        assert c.source_name == "naavik"

    def test_discover_and_collect(self):
        self._prime_inbox([
            {"url": "https://www.gamesindustry.biz/a", "title": "A",
             "summary": "gist", "email_subject": "GI Daily",
             "email_date": "Thu, 23 Jul 2026 15:25:16 +0000"},
        ])
        c = NewsletterCollector("gamesindustry.biz")
        urls = c.discover(limit=10)
        assert urls == ["https://www.gamesindustry.biz/a"]

        item = c.collect(urls[0])
        assert item.title == "A"
        assert item.content == "gist"
        assert item.source_type == "newsletter"
        assert item.source_name == "gamesindustry.biz"
        assert item.author == "gamesindustry.biz newsletter"

    def test_discover_respects_limit(self):
        self._prime_inbox([
            {"url": f"https://www.gamesindustry.biz/{i}", "title": str(i),
             "summary": "", "email_subject": "s", "email_date": None}
            for i in range(10)
        ])
        c = NewsletterCollector("gamesindustry.biz")
        assert len(c.discover(limit=3)) == 3

    def test_collect_uncached_returns_none(self):
        self._prime_inbox([])
        c = NewsletterCollector("gamesindustry.biz")
        assert c.collect("https://unknown.example.com") is None

    def test_discover_other_senders_bucket_empty(self):
        self._prime_inbox([{"url": "https://x/a", "title": "A", "summary": "",
                            "email_subject": "s", "email_date": None}])
        c = NewsletterCollector("naavik")
        assert c.discover(limit=10) == []


class TestExtractItemsFiltering:
    """_extract_items post-filtering of the model's JSON (client mocked)."""

    def _fake_response(self, text):
        class Block:
            type = "text"
        block = Block()
        block.text = text

        class Usage:
            input_tokens = 100
            output_tokens = 50

        class Response:
            content = [block]
            usage = Usage()
        return Response()

    @patch("src.sources.newsletter._resolve_url", side_effect=lambda u: u)
    @patch("src.summarizer.get_client")
    def test_junk_and_malformed_items_dropped(self, mock_client, mock_resolve):
        payload = """```json
        [
          {"url": "https://www.gamesindustry.biz/real", "title": "Real", "summary": "ok"},
          {"url": "https://x.com/gamesindustry", "title": "Social", "summary": ""},
          {"url": "https://gi.biz/unsubscribe?u=1", "title": "Unsub", "summary": ""},
          {"url": "not-a-url", "title": "Broken", "summary": ""},
          {"url": "https://gi.biz/no-title", "title": "", "summary": ""}
        ]
        ```"""
        mock_client.return_value.messages.create.return_value = self._fake_response(payload)
        items = newsletter._extract_items("<html></html>", "gamesindustry.biz", "subj")
        assert [i["title"] for i in items] == ["Real"]

    @patch("src.summarizer.get_client")
    def test_non_json_reply_returns_empty(self, mock_client):
        mock_client.return_value.messages.create.return_value = self._fake_response(
            "Sorry, I cannot help with that.")
        assert newsletter._extract_items("<html></html>", "naavik", "subj") == []


def test_get_newsletter_collectors_skips_blocked():
    names = [c.source_name for c in get_newsletter_collectors()]
    assert "gamesindustry.biz" in names
    assert "mobilegamer.biz" in names
    assert None not in names
    assert len(names) == len(set(names))
