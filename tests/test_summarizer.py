"""Tests for src/summarizer.py (mocked API calls)."""

import pytest
from unittest.mock import patch, MagicMock
from src.summarizer import (
    summarize_article, summarize_batch, cost_tracker,
    CostTracker, SummarizationError, APIKeyError, get_client,
)
from src.config import Config


@pytest.fixture(autouse=True)
def reset_cost_tracker():
    """Reset cost tracker before each test."""
    cost_tracker.reset()
    yield


def _make_mock_response(text="mock summary", input_tokens=100, output_tokens=50):
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    response.model = "claude-sonnet-4-20250514"
    return response


class TestCostTracker:
    def test_initial_state(self):
        ct = CostTracker()
        assert ct.total_requests == 0
        assert ct.total_input_tokens == 0
        assert ct.total_output_tokens == 0

    def test_add_usage(self):
        ct = CostTracker()
        ct.add_usage(500, 100)
        ct.add_usage(300, 50)
        assert ct.total_input_tokens == 800
        assert ct.total_output_tokens == 150
        assert ct.total_requests == 2

    def test_cost_estimate(self):
        ct = CostTracker()
        ct.add_usage(1_000_000, 1_000_000)
        costs = ct.get_cost_estimate()
        assert costs['input_cost'] == 3.0
        assert costs['output_cost'] == 15.0
        assert costs['total_cost'] == 18.0

    def test_reset(self):
        ct = CostTracker()
        ct.add_usage(500, 100)
        ct.reset()
        assert ct.total_requests == 0
        assert ct.total_input_tokens == 0

    def test_str_representation(self):
        ct = CostTracker()
        ct.add_usage(100, 50)
        s = str(ct)
        assert "1 requests" in s
        assert "100 input tokens" in s


class TestSummarizeArticle:
    @patch('src.summarizer.get_client')
    def test_summarize_returns_text(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(
            "bullet 1\nbullet 2\nbullet 3"
        )
        mock_get_client.return_value = mock_client

        result = summarize_article("Test Title", "Test content " * 50)
        assert "bullet 1" in result
        assert cost_tracker.total_requests == 1

    @patch('src.summarizer.get_client')
    def test_summarize_tracks_cost(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(
            input_tokens=500, output_tokens=100
        )
        mock_get_client.return_value = mock_client

        summarize_article("Title", "Content " * 50)
        assert cost_tracker.total_input_tokens == 500
        assert cost_tracker.total_output_tokens == 100

    @patch('src.summarizer.get_client')
    def test_summarize_uses_config_model(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response()
        mock_get_client.return_value = mock_client

        summarize_article("Title", "Content " * 50)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs['model'] == Config.CLAUDE_MODEL


class TestSummarizeBatch:
    @patch('src.summarizer.get_client')
    @patch('src.database.update_article_summary')
    def test_batch_processes_all(self, mock_update, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response("summary")
        mock_get_client.return_value = mock_client

        articles = [
            {'url': 'https://example.com/1', 'title': 'Article 1', 'content': 'Content 1 ' * 20},
            {'url': 'https://example.com/2', 'title': 'Article 2', 'content': 'Content 2 ' * 20},
        ]

        stats = summarize_batch(articles, db_path='test.db')
        assert stats['success'] == 2
        assert stats['failed'] == 0
        assert mock_update.call_count == 2

    @patch('src.summarizer.get_client')
    def test_batch_skips_no_content(self, mock_get_client):
        articles = [
            {'url': 'https://example.com/1', 'title': 'No Content', 'content': ''},
            {'url': 'https://example.com/2', 'title': 'Also None', 'content': None},
        ]

        stats = summarize_batch(articles)
        assert stats['skipped'] == 2
        assert stats['success'] == 0
