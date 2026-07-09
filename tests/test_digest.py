"""Tests for src/digest.py (mocked AI + fake DB rows)."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src import database
from src.digest import (
    generate_digest,
    compose_digest_html,
    find_latest_digest,
    _format_items,
    _strip_markdown_fences,
    CLOSING_LINE,
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
        assert "⚠️ Don't get burned" in prompt
        assert 'FOR GAMERS' in prompt


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
