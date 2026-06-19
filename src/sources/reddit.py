"""
Reddit collector — fetches hot/new posts from gaming subreddits via PRAW.

Read-only mode: only needs client_id + client_secret (no user login).
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from src.sources.base import BaseCollector, CollectedItem
from src.config import Config

logger = logging.getLogger(__name__)

# Subreddit configurations
REDDIT_SUBREDDITS = [
    "AndroidGaming",
    "MobileGaming",
    "iosgaming",
]


def _get_reddit_client():
    """Initialize PRAW Reddit client in read-only mode."""
    if not Config.REDDIT_CLIENT_ID or 'your_' in Config.REDDIT_CLIENT_ID.lower():
        raise ValueError("REDDIT_CLIENT_ID not configured in .env")

    import praw
    return praw.Reddit(
        client_id=Config.REDDIT_CLIENT_ID,
        client_secret=Config.REDDIT_CLIENT_SECRET,
        user_agent=Config.REDDIT_USER_AGENT,
    )


class RedditCollector(BaseCollector):
    """Collects posts from a subreddit."""

    source_type = "reddit"

    def __init__(self, subreddit: str):
        self.source_name = subreddit
        self._subreddit_name = subreddit
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = _get_reddit_client()
        return self._client

    def discover(self, limit: int = 20) -> List[str]:
        """Get hot post URLs from the subreddit, filtered by min score."""
        try:
            reddit = self._get_client()
            subreddit = reddit.subreddit(self._subreddit_name)

            post_urls = []
            # Fetch more than limit to account for filtering
            for post in subreddit.hot(limit=limit * 2):
                # Skip stickied posts
                if post.stickied:
                    continue

                # Skip low-quality posts
                if post.score < Config.REDDIT_MIN_SCORE:
                    continue

                post_urls.append(f"https://reddit.com{post.permalink}")

                if len(post_urls) >= limit:
                    break

            logger.info(f"[r/{self.source_name}] Discovered {len(post_urls)} posts")
            return post_urls

        except Exception as e:
            logger.error(f"[r/{self.source_name}] Failed to discover posts: {e}")
            return []

    def collect(self, post_url: str) -> Optional[CollectedItem]:
        """Fetch a single Reddit post."""
        try:
            reddit = self._get_client()
            submission = reddit.submission(url=post_url)

            # Build content: selftext for text posts, linked URL for link posts
            content = submission.selftext if submission.selftext else ""
            if not submission.is_self and submission.url:
                content = f"Link: {submission.url}\n\n{content}" if content else f"Link: {submission.url}"

            # Get image URL
            image_url = None
            if hasattr(submission, 'preview') and submission.preview:
                try:
                    images = submission.preview.get('images', [])
                    if images:
                        image_url = images[0]['source']['url'].replace('&amp;', '&')
                except (KeyError, IndexError):
                    pass

            if not image_url and submission.thumbnail and submission.thumbnail.startswith('http'):
                image_url = submission.thumbnail

            # Date
            date = datetime.fromtimestamp(
                submission.created_utc, tz=timezone.utc
            ).isoformat()

            # Author (can be None for deleted accounts)
            author = str(submission.author) if submission.author else "[deleted]"

            # Title with subreddit context and score
            title = submission.title

            return CollectedItem(
                url=f"https://reddit.com{submission.permalink}",
                title=title,
                date=date,
                author=f"u/{author} on r/{self._subreddit_name}",
                content=content if content else title,
                image_url=image_url,
                source_type='reddit',
                source_name=self._subreddit_name,
                content_id=submission.id,
            )

        except Exception as e:
            logger.error(f"[r/{self.source_name}] Failed to collect post: {e}")
            return None


def get_reddit_collectors() -> List[RedditCollector]:
    """Get collectors for all configured subreddits."""
    return [RedditCollector(sub) for sub in REDDIT_SUBREDDITS]
