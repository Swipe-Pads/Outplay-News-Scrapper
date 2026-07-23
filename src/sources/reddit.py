"""
Reddit collector — fetches hot posts from gaming subreddits via public RSS
(Atom) feeds. No credentials required.

Reddit's Responsible Builder Policy (2026) ended self-serve API app
registration, and the public *.json listings now return 403 even for
browser User-Agents. The Atom feeds (/r/<sub>/hot.rss) still work but are
aggressively rate-limited (429 after a few rapid requests), so this
collector makes exactly ONE request per subreddit and serves collect()
entirely from the cached listing.

Trade-offs vs the old PRAW version: no score data (REDDIT_MIN_SCORE cannot
be applied) and no stickied flag (AutoModerator posts are skipped as a
heuristic instead).
"""

import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import requests

from src.sources.base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

# Subreddit configurations
REDDIT_SUBREDDITS = [
    "AndroidGaming",
    "MobileGaming",
    "iosgaming",
]

_ATOM_NS = {
    'a': 'http://www.w3.org/2005/Atom',
    'm': 'http://search.yahoo.com/mrss/',
}
_TIMEOUT = 15
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 10

# Reddit blocks obviously-botty User-Agents on feed endpoints too; a browser
# UA is required. REDDIT_USER_AGENT from config is intentionally NOT used here.
_BROWSER_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
               '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')


def _fetch_feed(url: str, params: dict) -> bytes:
    """GET with retry/backoff for Reddit's 429 rate limiting."""
    last_error = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        response = requests.get(
            url, params=params,
            headers={'User-Agent': _BROWSER_UA},
            timeout=_TIMEOUT,
        )
        if response.status_code == 200 and response.content:
            return response.content
        last_error = f"HTTP {response.status_code}"
        if attempt < _MAX_ATTEMPTS:
            wait = _BACKOFF_SECONDS * attempt
            logger.warning(f"Reddit feed {url} returned {last_error}, "
                           f"retrying in {wait}s (attempt {attempt}/{_MAX_ATTEMPTS})")
            time.sleep(wait)
    raise RuntimeError(f"Reddit feed failed after {_MAX_ATTEMPTS} attempts: {last_error}")


def _entry_to_post(entry: ET.Element) -> Optional[dict]:
    """Convert one Atom <entry> into a plain dict of post fields."""
    link_el = entry.find('a:link', _ATOM_NS)
    title_el = entry.find('a:title', _ATOM_NS)
    if link_el is None or title_el is None:
        return None

    author_el = entry.find('a:author/a:name', _ATOM_NS)
    # Feed format is "/u/username"
    author = (author_el.text or '').lstrip('/').removeprefix('u/') if author_el is not None else ''

    date_el = entry.find('a:published', _ATOM_NS)
    if date_el is None:
        date_el = entry.find('a:updated', _ATOM_NS)
    id_el = entry.find('a:id', _ATOM_NS)
    content_el = entry.find('a:content', _ATOM_NS)
    content_html = html.unescape(content_el.text or '') if content_el is not None else ''

    # Image: prefer media:thumbnail, else first <img> in the content HTML
    thumb_el = entry.find('m:thumbnail', _ATOM_NS)
    image_url = thumb_el.get('url') if thumb_el is not None else None
    if not image_url:
        img_match = _IMG_RE.search(content_html)
        if img_match:
            image_url = html.unescape(img_match.group(1))

    # Content: the feed's HTML body stripped to plain text (boilerplate
    # "[link] [comments]" suffix removed)
    text = _TAG_RE.sub(' ', content_html)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'submitted by\s+/u/\S+.*$', '', text).strip()

    return {
        'url': link_el.get('href'),
        'title': title_el.text or '',
        'author': author or '[deleted]',
        'date': date_el.text if date_el is not None else None,
        # Atom id is "t3_<postid>"
        'content_id': (id_el.text or '').removeprefix('t3_') if id_el is not None else None,
        'content': text,
        'image_url': image_url,
    }


class RedditCollector(BaseCollector):
    """Collects posts from a subreddit."""

    source_type = "reddit"

    def __init__(self, subreddit: str):
        self.source_name = subreddit
        self._subreddit_name = subreddit
        # Post dicts cached by URL — collect() never makes its own request
        self._posts: Dict[str, dict] = {}

    def discover(self, limit: int = 20) -> List[str]:
        """Get hot post URLs from the subreddit's Atom feed."""
        try:
            content = _fetch_feed(
                f"https://www.reddit.com/r/{self._subreddit_name}/hot.rss",
                params={'limit': min(limit + 5, 25)},
            )
            root = ET.fromstring(content)

            post_urls = []
            for entry in root.findall('a:entry', _ATOM_NS):
                post = _entry_to_post(entry)
                if post is None or not post['url']:
                    continue

                # No stickied flag in RSS — skip AutoModerator threads instead
                if post['author'] == 'AutoModerator':
                    continue

                self._posts[post['url']] = post
                post_urls.append(post['url'])

                if len(post_urls) >= limit:
                    break

            logger.info(f"[r/{self.source_name}] Discovered {len(post_urls)} posts")
            return post_urls

        except Exception as e:
            logger.error(f"[r/{self.source_name}] Failed to discover posts: {e}")
            return []

    def collect(self, post_url: str) -> Optional[CollectedItem]:
        """Build a CollectedItem from the cached feed entry."""
        post = self._posts.get(post_url)
        if post is None:
            # Deliberately no fallback fetch: per-post requests trip Reddit's
            # rate limiter (429) and would poison the whole run.
            logger.warning(f"[r/{self.source_name}] Post not in feed cache, "
                           f"skipping: {post_url}")
            return None

        return CollectedItem(
            url=post['url'],
            title=post['title'],
            date=post['date'],
            author=f"u/{post['author']} on r/{self._subreddit_name}",
            content=post['content'] or post['title'],
            image_url=post['image_url'],
            source_type='reddit',
            source_name=self._subreddit_name,
            content_id=post['content_id'],
        )


def get_reddit_collectors() -> List[RedditCollector]:
    """Get collectors for all configured subreddits."""
    return [RedditCollector(sub) for sub in REDDIT_SUBREDDITS]
