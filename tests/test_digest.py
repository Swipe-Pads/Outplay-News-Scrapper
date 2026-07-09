"""Tests for src/digest.py (mocked AI + fake DB rows)."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src import database
from src.digest import (
    generate_digest,
    compose_digest_html,
    compose_excerpt,
    find_latest_digest,
    is_deal_article,
    find_deal_articles,
    _format_items,
    _strip_markdown_fences,
    CLOSING_LINE,
    EXCERPT_SUFFIX,
    DigestError,
)

SAMPLE_HTML = (
    '<p><em>Your weekly briefing on what actually matters in mobile gaming.</em></p>\n'
    '<h2>🔥 Play this week</h2>\n'
    '<ul><li><strong>Big launch</strong> — go play it now. '
    '<a href="https://example.com/1">Pocket Gamer</a></li></ul>\n'
    + CLOSING_LINE
)


def _make_mock_response(text, input_tokens=500, output_tokens=800):
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(str(db_path))
    return str(db_path)


def _insert_scored_articles(db_path, count=3):
    now = datetime.now(timezone.utc).isoformat()
    for i in range(count):
        database.insert_article({
            'url': f'https://example.com/{i}',
            'title': f'Scored Article {i}',
            'content': f'Content for article {i} ' * 20,
            'summary': f'Summary {i}',
            'date': now,
            'source_type': 'website',
            'source_name': 'pocketgamer',
        }, db_path)
        database.update_article_score(f'https://example.com/{i}', 90.0 - i, db_path)


# === Helpers ===

class TestHelpers:
    def test_format_items_includes_url_and_source(self):
        articles = [{
            'title': 'Test', 'source_name': 'pocketgamer', 'source_type': 'website',
            'date': '2026-07-01', 'url': 'https://example.com/x',
            'summary': 'Short summary',
        }]
        text = _format_items(articles)
        assert 'https://example.com/x' in text
        assert 'pocketgamer' in text
        assert 'Short summary' in text

    def test_strip_markdown_fences(self):
        wrapped = "```html\n<p>Hello</p>\n```"
        assert _strip_markdown_fences(wrapped) == "<p>Hello</p>"

    def test_strip_leaves_plain_html(self):
        assert _strip_markdown_fences("<p>Hi</p>") == "<p>Hi</p>"


# === compose_digest_html (mocked AI) ===

class TestComposeDigestHtml:
    @patch('src.summarizer.get_client')
    def test_returns_html_with_closing_line(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(SAMPLE_HTML)
        mock_get_client.return_value = mock_client

        html = compose_digest_html([{'title': 'A', 'url': 'https://e.com/1'}])
        assert '<h2>' in html
        assert CLOSING_LINE in html

    @patch('src.summarizer.get_client')
    def test_appends_missing_closing_line(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(
            '<p><em>Intro</em></p><h2>🔥 Play this week</h2><ul><li>Item</li></ul>'
        )
        mock_get_client.return_value = mock_client

        html = compose_digest_html([{'title': 'A', 'url': 'https://e.com/1'}])
        assert CLOSING_LINE in html

    @patch('src.summarizer.get_client')
    def test_empty_response_raises(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response("   ")
        mock_get_client.return_value = mock_client

        with pytest.raises(DigestError):
            compose_digest_html([{'title': 'A', 'url': 'https://e.com/1'}])

    @patch('src.summarizer.get_client')
    def test_prompt_contains_articles_and_sections(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(SAMPLE_HTML)
        mock_get_client.return_value = mock_client

        compose_digest_html([{'title': 'Unique Title XYZ', 'url': 'https://e.com/1'}])

        prompt = mock_client.messages.create.call_args[1]['messages'][0]['content']
        assert 'Unique Title XYZ' in prompt
        assert '🔥 Play this week' in prompt
        assert '💸 Deals worth grabbing' in prompt
        assert "⚠️ Don't get burned" in prompt
        assert 'FOR GAMERS' in prompt

    @patch('src.summarizer.get_client')
    def test_coming_soon_section_includes_out_now(self, mock_get_client):
        """🕹️ section spec: out-now (past 7 days) releases first, then coming soon."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(SAMPLE_HTML)
        mock_get_client.return_value = mock_client

        compose_digest_html([{'title': 'A', 'url': 'https://e.com/1'}])

        prompt = mock_client.messages.create.call_args[1]['messages'][0]['content']
        assert 'RELEASED in the past 7 days' in prompt
        assert 'out-now releases FIRST' in prompt


# === generate_digest (fake DB rows) ===

class TestGenerateDigest:
    @patch('src.summarizer.get_client')
    def test_generates_file_from_scored_articles(self, mock_get_client, temp_db, tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(SAMPLE_HTML)
        mock_get_client.return_value = mock_client

        _insert_scored_articles(temp_db)
        out_dir = tmp_path / "digests"

        path = generate_digest(since_days=7, db_path=temp_db, output_dir=out_dir)

        assert path.exists()
        assert path.name == f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-digest.html"
        content = path.read_text(encoding='utf-8')
        assert CLOSING_LINE in content

    @patch('src.summarizer.get_client')
    def test_falls_back_to_recent_when_unscored(self, mock_get_client, temp_db, tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(SAMPLE_HTML)
        mock_get_client.return_value = mock_client

        # Insert articles WITHOUT scores
        database.insert_article({
            'url': 'https://example.com/unscored', 'title': 'Unscored Article',
            'content': 'Content ' * 20, 'date': datetime.now(timezone.utc).isoformat(),
        }, temp_db)

        path = generate_digest(since_days=7, db_path=temp_db, output_dir=tmp_path / "d")
        assert path.exists()

    def test_no_articles_raises(self, temp_db, tmp_path):
        with pytest.raises(DigestError):
            generate_digest(since_days=7, db_path=temp_db, output_dir=tmp_path / "d")

    @patch('src.summarizer.get_client')
    def test_digest_uses_top_scored_first(self, mock_get_client, temp_db, tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(SAMPLE_HTML)
        mock_get_client.return_value = mock_client

        _insert_scored_articles(temp_db, count=3)
        generate_digest(since_days=7, top_n=2, db_path=temp_db, output_dir=tmp_path / "d")

        prompt = mock_client.messages.create.call_args[1]['messages'][0]['content']
        # top_n=2 -> highest scored (0 and 1) included, lowest (2) excluded
        assert 'Scored Article 0' in prompt
        assert 'Scored Article 1' in prompt
        assert 'Scored Article 2' not in prompt


# === Deals (💸 section) ===

class TestDealDetection:
    @pytest.mark.parametrize("title", [
        "Huge summer sale hits the App Store",
        "This roguelike is 60% off right now",
        "Monument Valley is free for a limited time",
        "Price drop: Dead Cells mobile",
        "Best deals this week on Android games",
        "Slay the Spire goes free on iOS",
    ])
    def test_deal_titles_detected(self, title):
        assert is_deal_article({'title': title, 'content': ''}) is True

    @pytest.mark.parametrize("title", [
        "CoD Mobile Season 6 launches with Persona collab",
        "PUBG Mobile World Cup teams locked",
        "New battle royale map confirmed",
    ])
    def test_non_deal_titles_ignored(self, title):
        assert is_deal_article({'title': title, 'content': ''}) is False

    def test_deal_detected_in_content(self):
        article = {
            'title': 'Weekly roundup',
            'content': 'Grab it now — 75% off until Sunday on the Play Store.',
        }
        assert is_deal_article(article) is True

    def test_find_deal_articles_from_db(self, temp_db):
        now = datetime.now(timezone.utc).isoformat()
        database.insert_article({
            'url': 'https://reddit.com/r/iosgaming/sale-thread',
            'title': 'Weekly App Store sale thread — big discounts',
            'content': 'Games on sale this week', 'date': now,
            'source_type': 'reddit', 'source_name': 'iosgaming',
        }, temp_db)
        database.insert_article({
            'url': 'https://example.com/not-a-deal',
            'title': 'New season starts in CoD Mobile',
            'content': 'Season details', 'date': now,
        }, temp_db)

        deals = find_deal_articles(7, temp_db)
        assert len(deals) == 1
        assert deals[0]['url'] == 'https://reddit.com/r/iosgaming/sale-thread'

    def test_find_deal_articles_excludes_urls(self, temp_db):
        now = datetime.now(timezone.utc).isoformat()
        database.insert_article({
            'url': 'https://example.com/deal',
            'title': 'Massive discount weekend', 'content': 'sale', 'date': now,
        }, temp_db)

        deals = find_deal_articles(7, temp_db, exclude_urls={'https://example.com/deal'})
        assert deals == []

    def test_format_items_marks_deals(self):
        articles = [
            {'title': 'Game is 50% off this weekend', 'url': 'https://e.com/deal'},
            {'title': 'New season launches', 'url': 'https://e.com/news'},
        ]
        text = _format_items(articles)
        lines = text.split('\n')
        assert lines[0].startswith('- [DEAL] ')
        assert '[DEAL]' not in lines[1]

    @patch('src.summarizer.get_client')
    def test_generate_digest_pulls_in_deal_articles(self, mock_get_client, temp_db, tmp_path):
        """Deal articles outside the top-N selection still reach the prompt."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(SAMPLE_HTML)
        mock_get_client.return_value = mock_client

        _insert_scored_articles(temp_db, count=2)
        # Unscored deal article — would never make the top-N cut
        database.insert_article({
            'url': 'https://example.com/hidden-deal',
            'title': 'Hidden gem is free for a limited time',
            'content': 'Premium game gone free', 'date': datetime.now(timezone.utc).isoformat(),
        }, temp_db)

        generate_digest(since_days=7, db_path=temp_db, output_dir=tmp_path / "d")

        prompt = mock_client.messages.create.call_args[1]['messages'][0]['content']
        assert 'Hidden gem is free for a limited time' in prompt
        assert '[DEAL]' in prompt


# === compose_excerpt (summary_html) ===

class TestComposeExcerpt:
    @patch('src.summarizer.get_client')
    def test_excerpt_returned_with_suffix(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(
            f"CoD Mobile just went full Persona — and that's not even half of it. {EXCERPT_SUFFIX}"
        )
        mock_get_client.return_value = mock_client

        excerpt = compose_excerpt("<p>digest body</p>")
        assert excerpt.endswith(EXCERPT_SUFFIX)
        assert 'Persona' in excerpt

    @patch('src.summarizer.get_client')
    def test_suffix_appended_when_missing(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(
            "Big week for mobile gamers."
        )
        mock_get_client.return_value = mock_client

        excerpt = compose_excerpt("<p>digest body</p>")
        assert excerpt.endswith(EXCERPT_SUFFIX)

    @patch('src.summarizer.get_client')
    def test_ai_failure_returns_fallback(self, mock_get_client):
        mock_get_client.side_effect = RuntimeError("no API key")

        excerpt = compose_excerpt("<p>digest body</p>")
        assert excerpt.endswith(EXCERPT_SUFFIX)
        assert len(excerpt) > len(EXCERPT_SUFFIX)


# === find_latest_digest ===

class TestFindLatestDigest:
    def test_finds_newest_by_date(self, tmp_path):
        d = tmp_path / "digests"
        d.mkdir()
        (d / "2026-06-22-digest.html").write_text("old", encoding='utf-8')
        (d / "2026-06-29-digest.html").write_text("new", encoding='utf-8')

        latest = find_latest_digest(d)
        assert latest.name == "2026-06-29-digest.html"

    def test_empty_dir_returns_none(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert find_latest_digest(d) is None

    def test_missing_dir_returns_none(self, tmp_path):
        assert find_latest_digest(tmp_path / "nope") is None
