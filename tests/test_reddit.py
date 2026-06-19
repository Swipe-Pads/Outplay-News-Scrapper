"""Tests for src/sources/reddit.py"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.sources.reddit import (
    RedditCollector,
    REDDIT_SUBREDDITS,
    get_reddit_collectors,
)


def _make_mock_post(
    title="Test Post",
    score=100,
    stickied=False,
    selftext="Post content",
    is_self=True,
    permalink="/r/AndroidGaming/comments/abc/test_post/",
    post_id="abc",
    author="testuser",
    url=None,
    thumbnail=None,
    preview=None,
    created_utc=None,
):
    post = MagicMock()
    post.title = title
    post.score = score
    post.stickied = stickied
    post.selftext = selftext
    post.is_self = is_self
    post.permalink = permalink
    post.id = post_id
    post.author = MagicMock(__str__=lambda s: author) if author else None
    post.url = url or f"https://reddit.com{permalink}"
    post.thumbnail = thumbnail
    post.preview = preview
    post.created_utc = created_utc or datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    return post


class TestRedditCollector:
    def test_init(self):
        c = RedditCollector("AndroidGaming")
        assert c.source_type == "reddit"
        assert c.source_name == "AndroidGaming"

    @patch('src.sources.reddit._get_reddit_client')
    def test_discover_filters_stickied(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit

        posts = [
            _make_mock_post(title="Stickied", stickied=True, permalink="/r/AG/s/"),
            _make_mock_post(title="Normal", stickied=False, permalink="/r/AG/n/"),
        ]
        mock_reddit.subreddit.return_value.hot.return_value = posts

        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=10)
        assert len(urls) == 1
        assert "/r/AG/n/" in urls[0]

    @patch('src.sources.reddit._get_reddit_client')
    def test_discover_filters_low_score(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit

        posts = [
            _make_mock_post(title="Low", score=1),
            _make_mock_post(title="High", score=100, permalink="/r/AG/h/"),
        ]
        mock_reddit.subreddit.return_value.hot.return_value = posts

        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=10)
        assert len(urls) == 1

    @patch('src.sources.reddit._get_reddit_client')
    def test_discover_respects_limit(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit

        posts = [
            _make_mock_post(permalink=f"/r/AG/{i}/") for i in range(10)
        ]
        mock_reddit.subreddit.return_value.hot.return_value = posts

        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=3)
        assert len(urls) == 3

    @patch('src.sources.reddit._get_reddit_client')
    def test_collect_self_post(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit

        mock_submission = _make_mock_post(
            title="Game Review",
            selftext="Great game!",
            is_self=True,
            post_id="xyz",
        )
        mock_reddit.submission.return_value = mock_submission

        c = RedditCollector("AndroidGaming")
        item = c.collect("https://reddit.com/r/AG/comments/xyz/")
        assert item is not None
        assert item.title == "Game Review"
        assert item.source_type == "reddit"
        assert item.content_id == "xyz"
        assert "Great game!" in item.content

    @patch('src.sources.reddit._get_reddit_client')
    def test_collect_link_post(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit

        mock_submission = _make_mock_post(
            title="External Link",
            selftext="",
            is_self=False,
            url="https://example.com/article",
        )
        mock_reddit.submission.return_value = mock_submission

        c = RedditCollector("AndroidGaming")
        item = c.collect("https://reddit.com/r/AG/comments/abc/")
        assert item is not None
        assert "https://example.com/article" in item.content

    @patch('src.sources.reddit._get_reddit_client')
    def test_collect_with_thumbnail(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit

        mock_submission = _make_mock_post(
            thumbnail="https://img.com/thumb.jpg",
        )
        mock_submission.preview = None
        mock_reddit.submission.return_value = mock_submission

        c = RedditCollector("AndroidGaming")
        item = c.collect("https://reddit.com/r/AG/comments/abc/")
        assert item.image_url == "https://img.com/thumb.jpg"

    @patch('src.sources.reddit._get_reddit_client')
    def test_collect_handles_deleted_author(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit

        mock_submission = _make_mock_post(author=None)
        mock_submission.author = None
        mock_reddit.submission.return_value = mock_submission

        c = RedditCollector("AndroidGaming")
        item = c.collect("https://reddit.com/r/AG/comments/abc/")
        assert "[deleted]" in item.author

    @patch('src.sources.reddit._get_reddit_client')
    def test_collect_returns_none_on_error(self, mock_client_factory):
        mock_reddit = MagicMock()
        mock_client_factory.return_value = mock_reddit
        mock_reddit.submission.side_effect = Exception("API error")

        c = RedditCollector("AndroidGaming")
        result = c.collect("https://reddit.com/r/AG/comments/bad/")
        assert result is None


class TestGetRedditCollectors:
    def test_returns_all_subreddits(self):
        collectors = get_reddit_collectors()
        assert len(collectors) == len(REDDIT_SUBREDDITS)
        names = [c.source_name for c in collectors]
        assert "AndroidGaming" in names
        assert "MobileGaming" in names
        assert "iosgaming" in names
