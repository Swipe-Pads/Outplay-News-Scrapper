"""Tests for src/sources/reddit.py (public RSS/Atom feed implementation)"""

from unittest.mock import patch

from src.sources.reddit import (
    RedditCollector,
    REDDIT_SUBREDDITS,
    get_reddit_collectors,
)


def _make_entry(
    title="Test Post",
    author="testuser",
    permalink="/r/AndroidGaming/comments/abc/test_post/",
    post_id="abc",
    published="2026-07-20T10:00:00+00:00",
    content_html="&lt;p&gt;Post content&lt;/p&gt;",
    thumbnail=None,
):
    thumb = f'<media:thumbnail url="{thumbnail}" />' if thumbnail else ''
    return f"""
    <entry>
        <author><name>/u/{author}</name><uri>https://www.reddit.com/user/{author}</uri></author>
        <id>t3_{post_id}</id>
        {thumb}
        <link href="https://www.reddit.com{permalink}" />
        <published>{published}</published>
        <updated>{published}</updated>
        <title>{title}</title>
        <content type="html">{content_html}</content>
    </entry>
    """


def _make_feed(entries):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:media="http://search.yahoo.com/mrss/">'
        + "".join(entries) +
        '</feed>'
    ).encode('utf-8')


class TestRedditCollector:
    def test_init(self):
        c = RedditCollector("AndroidGaming")
        assert c.source_type == "reddit"
        assert c.source_name == "AndroidGaming"

    @patch('src.sources.reddit._fetch_feed')
    def test_discover_skips_automoderator(self, mock_fetch):
        mock_fetch.return_value = _make_feed([
            _make_entry(title="Weekly Thread", author="AutoModerator",
                        permalink="/r/AG/comments/s/weekly/", post_id="s"),
            _make_entry(title="Normal", permalink="/r/AG/comments/n/normal/",
                        post_id="n"),
        ])
        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=10)
        assert len(urls) == 1
        assert "/comments/n/" in urls[0]

    @patch('src.sources.reddit._fetch_feed')
    def test_discover_respects_limit(self, mock_fetch):
        mock_fetch.return_value = _make_feed([
            _make_entry(permalink=f"/r/AG/comments/{i}/p/", post_id=str(i))
            for i in range(10)
        ])
        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=3)
        assert len(urls) == 3

    @patch('src.sources.reddit._fetch_feed')
    def test_discover_returns_empty_on_error(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("HTTP 429")
        c = RedditCollector("AndroidGaming")
        assert c.discover(limit=10) == []

    @patch('src.sources.reddit._fetch_feed')
    def test_collect_from_cache(self, mock_fetch):
        mock_fetch.return_value = _make_feed([
            _make_entry(
                title="Game Review",
                content_html="&lt;p&gt;Great game!&lt;/p&gt; submitted by /u/testuser",
                post_id="xyz",
                permalink="/r/AG/comments/xyz/review/",
            ),
        ])
        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=10)
        item = c.collect(urls[0])
        assert item is not None
        assert item.title == "Game Review"
        assert item.source_type == "reddit"
        assert item.content_id == "xyz"
        assert "Great game!" in item.content
        assert "submitted by" not in item.content
        assert item.author == "u/testuser on r/AndroidGaming"
        assert item.date == "2026-07-20T10:00:00+00:00"

    @patch('src.sources.reddit._fetch_feed')
    def test_collect_with_media_thumbnail(self, mock_fetch):
        mock_fetch.return_value = _make_feed([
            _make_entry(thumbnail="https://img.com/thumb.jpg"),
        ])
        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=10)
        item = c.collect(urls[0])
        assert item.image_url == "https://img.com/thumb.jpg"

    @patch('src.sources.reddit._fetch_feed')
    def test_collect_image_from_content_html(self, mock_fetch):
        mock_fetch.return_value = _make_feed([
            _make_entry(
                content_html='&lt;img src="https://preview.redd.it/pic.jpg?width=640&amp;amp;s=x" /&gt;'
            ),
        ])
        c = RedditCollector("AndroidGaming")
        urls = c.discover(limit=10)
        item = c.collect(urls[0])
        assert item.image_url == "https://preview.redd.it/pic.jpg?width=640&s=x"

    def test_collect_uncached_returns_none(self):
        c = RedditCollector("AndroidGaming")
        assert c.collect("https://reddit.com/r/AG/comments/bad/") is None


class TestGetRedditCollectors:
    def test_returns_all_subreddits(self):
        collectors = get_reddit_collectors()
        assert len(collectors) == len(REDDIT_SUBREDDITS)
        names = [c.source_name for c in collectors]
        assert "AndroidGaming" in names
        assert "MobileGaming" in names
        assert "iosgaming" in names
