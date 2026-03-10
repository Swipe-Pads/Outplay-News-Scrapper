"""
Reddit Data API client for gaming news scraper pipeline.

Uses OAuth2 client credentials flow (application-only authentication) to scrape
gaming subreddits without requiring user context. Supports flair filtering, rate
limiting, and robust error handling.

Rate limits: Reddit API allows 100 requests per minute.
"""

import logging
import os
import time
from datetime import datetime
from typing import List, Optional

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

from . import ScrapedContent


logger = logging.getLogger(__name__)
load_dotenv()


class RedditScraper:
    """Reddit API client using OAuth2 client credentials flow."""

    BASE_URL = "https://www.reddit.com"
    API_BASE_URL = "https://oauth.reddit.com"
    TOKEN_ENDPOINT = "https://www.reddit.com/api/v1/access_token"

    # User-Agent is required by Reddit API and should identify your app
    USER_AGENT = "OutplayNewsScraper/1.0 (by /u/OutplayApp)"

    # Rate limiting: sleep between requests (100 req/min = 1 req per 0.6 sec)
    REQUEST_INTERVAL = 0.6

    def __init__(self):
        """Initialize Reddit scraper with OAuth2 credentials from environment."""
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.access_token = None
        self.token_expiry = None
        self.last_request_time = 0

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set in environment"
            )

        logger.info("RedditScraper initialized")

    def _get_access_token(self) -> str:
        """
        Obtain or refresh OAuth2 access token using client credentials flow.

        Returns:
            str: Valid access token for API requests.

        Raises:
            requests.RequestException: If token request fails.
        """
        try:
            auth = HTTPBasicAuth(self.client_id, self.client_secret)
            data = {"grant_type": "client_credentials"}
            headers = {"User-Agent": self.USER_AGENT}

            response = requests.post(
                self.TOKEN_ENDPOINT,
                auth=auth,
                data=data,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.token_expiry = time.time() + token_data["expires_in"]

            logger.debug("Successfully obtained Reddit access token")
            return self.access_token

        except requests.RequestException as e:
            logger.error(f"Failed to obtain Reddit access token: {e}")
            raise

    def _ensure_valid_token(self) -> str:
        """
        Ensure access token is valid, refresh if expired.

        Returns:
            str: Valid access token.
        """
        if (
            self.access_token is None
            or self.token_expiry is None
            or time.time() >= self.token_expiry
        ):
            logger.debug("Access token expired or not set, refreshing...")
            return self._get_access_token()
        return self.access_token

    def _rate_limit(self) -> None:
        """Apply rate limiting to respect Reddit API constraints."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Make authenticated request to Reddit API.

        Args:
            endpoint: API endpoint path (e.g., "/r/CoDMCompetitive/hot")
            params: Query parameters for the request.

        Returns:
            dict: Parsed JSON response.

        Raises:
            requests.RequestException: If request fails.
        """
        self._rate_limit()
        token = self._ensure_valid_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.USER_AGENT,
        }

        url = f"{self.API_BASE_URL}{endpoint}"

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Reddit API request failed: {e}")
            raise

    def _extract_image_url(self, post: dict) -> Optional[str]:
        """
        Extract best available image URL from Reddit post.

        Tries in order:
        1. preview.images[0].source.url (high quality)
        2. thumbnail field
        3. url field (for link posts to images)

        Args:
            post: Reddit post data object.

        Returns:
            str: Image URL if found, None otherwise.
        """
        # Try preview images first
        if "preview" in post and "images" in post["preview"]:
            try:
                preview_url = post["preview"]["images"][0]["source"]["url"]
                # Unescape HTML entities
                return preview_url.replace("&amp;", "&")
            except (IndexError, KeyError):
                pass

        # Try thumbnail
        if post.get("thumbnail") and post["thumbnail"] not in ["self", "default", ""]:
            return post["thumbnail"]

        # Try post URL if it's an image
        post_url = post.get("url", "")
        if post_url and any(
            post_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"]
        ):
            return post_url

        return None

    def _determine_content_type(self, post: dict) -> str:
        """
        Determine initial content type based on post structure.

        Args:
            post: Reddit post data object.

        Returns:
            str: Content type ("news", "video", "community").
        """
        is_video = post.get("is_video", False)
        if is_video or post.get("media"):
            return "video"

        is_self = post.get("is_self", False)
        if is_self:
            return "community"

        return "news"

    def scrape_subreddit(
        self,
        subreddit: str,
        flair_filters: Optional[List[str]] = None,
        sort: str = "hot",
        time_filter: str = "day",
        limit: int = 15,
    ) -> List[ScrapedContent]:
        """
        Scrape posts from a subreddit.

        Args:
            subreddit: Subreddit name (e.g., "CoDMCompetitive", "gaming").
            flair_filters: Optional list of flair text to include
                          (e.g., ["News", "Update", "Announcement"]).
                          If provided, only posts matching one of these flairs are included.
            sort: Sort order ("hot", "new", "top", "rising", "controversial").
            time_filter: Time filter for top/controversial
                        ("all", "day", "week", "month", "year").
            limit: Maximum number of posts to retrieve (default 15).

        Returns:
            List[ScrapedContent]: Normalized scraped posts.

        Raises:
            ValueError: If subreddit or parameters are invalid.
            requests.RequestException: If API request fails.
        """
        if not subreddit or not isinstance(subreddit, str):
            raise ValueError("subreddit must be a non-empty string")

        if sort not in ["hot", "new", "top", "rising", "controversial"]:
            raise ValueError(f"Invalid sort: {sort}")

        if time_filter not in ["all", "day", "week", "month", "year"]:
            raise ValueError(f"Invalid time_filter: {time_filter}")

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        logger.info(
            f"Scraping subreddit r/{subreddit} (sort={sort}, limit={limit})"
        )

        endpoint = f"/r/{subreddit}/{sort}"
        params = {
            "limit": min(limit, 100),
        }

        if sort in ["top", "controversial"]:
            params["t"] = time_filter

        try:
            data = self._make_request(endpoint, params)
        except requests.RequestException as e:
            logger.error(f"Failed to scrape r/{subreddit}: {e}")
            return []

        posts = data.get("data", {}).get("children", [])
        logger.debug(f"Retrieved {len(posts)} posts from r/{subreddit}")

        scraped_content = []

        for post_wrapper in posts:
            try:
                post = post_wrapper.get("data", {})

                # Skip deleted/removed posts
                if post.get("author") == "[deleted]" or post.get("removed"):
                    logger.debug(f"Skipping deleted/removed post: {post.get('id')}")
                    continue

                # Skip NSFW if needed
                if post.get("over_18", False):
                    logger.debug(f"Skipping NSFW post: {post.get('id')}")
                    continue

                # Apply flair filtering if specified
                flair_text = post.get("link_flair_text", "")
                if flair_filters and flair_text not in flair_filters:
                    logger.debug(
                        f"Post {post.get('id')} flair '{flair_text}' not in filters"
                    )
                    continue

                # Extract content
                title = post.get("title", "").strip()
                body = post.get("selftext", "").strip()
                author = post.get("author", "Unknown")
                score = post.get("score", 0)
                post_url = f"https://reddit.com{post.get('permalink', '')}"
                created_utc = post.get("created_utc", 0)
                image_url = self._extract_image_url(post)

                # Skip empty posts
                if not title:
                    logger.debug(f"Skipping empty post: {post.get('id')}")
                    continue

                # Build ScrapedContent
                content: ScrapedContent = {
                    "source_type": "reddit",
                    "source_url": post_url,
                    "source_name": f"Reddit r/{subreddit}",
                    "title": title,
                    "body": body,
                    "original_author": author,
                    "score": score,
                    "content_type": self._determine_content_type(post),
                    "scraped_at": datetime.utcnow().isoformat() + "Z",
                    "source_published_at": datetime.utcfromtimestamp(
                        created_utc
                    ).isoformat()
                    + "Z",
                }

                if image_url:
                    content["image_url"] = image_url

                scraped_content.append(content)
                logger.debug(f"Scraped post: {title[:50]}...")

            except Exception as e:
                logger.warning(f"Error processing post: {e}")
                continue

        logger.info(f"Successfully scraped {len(scraped_content)} posts from r/{subreddit}")
        return scraped_content


def main():
    """Standalone testing of Reddit scraper."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        scraper = RedditScraper()

        # Example: scrape gaming subreddit
        posts = scraper.scrape_subreddit(
            subreddit="gaming",
            flair_filters=None,
            sort="hot",
            limit=5,
        )

        for post in posts:
            print(f"\n{post['source_name']}")
            print(f"Title: {post['title']}")
            print(f"Author: {post['original_author']}")
            print(f"Score: {post['score']}")
            print(f"URL: {post['source_url']}")

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    main()
