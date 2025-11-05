"""
Twitter/X scraper implementation.
Scrapes tweets from Twitter profiles using Playwright with fallback support.
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag

from src.social.base_scraper import BaseSocialScraper
from src.social.content_classifier import (
    classify_post_type,
    extract_hashtags,
    extract_mentions,
    extract_media_urls,
    extract_youtube_id
)


class TwitterScraper(BaseSocialScraper):
    """
    Twitter/X profile scraper.

    Scrapes tweets from public Twitter profiles, extracting:
    - Tweet text and metadata
    - Images, videos, YouTube links
    - Engagement metrics (likes, retweets, replies, views)
    - Hashtags and mentions
    """

    PLATFORM_NAME = "twitter"

    async def scrape_profile(
        self,
        profile_url: str,
        game_name: str,
        fallback_file: Optional[str] = None
    ) -> List[Dict]:
        """
        Scrape tweets from a Twitter profile.

        Args:
            profile_url: Twitter profile URL (e.g., https://x.com/USERNAME)
            game_name: Name of the game (for database)
            fallback_file: Path to fallback HTML file

        Returns:
            List of parsed tweet dictionaries
        """
        print(f"\n🐦 Scraping Twitter profile: {profile_url}")
        print(f"   Game: {game_name}")

        # Fetch page HTML
        html_content = await self.fetch_page(
            url=profile_url,
            fallback_file=fallback_file,
            wait_for='article[data-testid="tweet"]'
        )

        # Parse tweets
        tweets = self.parse_posts(html_content, game_name)

        print(f"✅ Scraped {len(tweets)} tweets from {profile_url}")
        return tweets

    def parse_posts(self, html_content: str, game_name: str) -> List[Dict]:
        """
        Parse tweets from HTML content.

        Args:
            html_content: Raw HTML from Twitter page
            game_name: Name of the game

        Returns:
            List of tweet dictionaries
        """
        soup = BeautifulSoup(html_content, 'lxml')

        # Find all tweet elements
        tweet_elements = soup.find_all('article', {'data-testid': 'tweet'})

        print(f"   Found {len(tweet_elements)} tweet elements in HTML")

        tweets = []
        for idx, tweet_element in enumerate(tweet_elements, 1):
            try:
                tweet_data = self._parse_single_tweet(tweet_element, game_name)
                if tweet_data:
                    tweets.append(tweet_data)
                    print(f"   ✓ Parsed tweet {idx}/{len(tweet_elements)}: {tweet_data['post_type']}")
            except Exception as e:
                print(f"   ⚠️  Error parsing tweet {idx}: {e}")
                continue

        return tweets

    def _parse_single_tweet(self, tweet_element: Tag, game_name: str) -> Optional[Dict]:
        """
        Parse a single tweet element.

        Args:
            tweet_element: BeautifulSoup element for the tweet
            game_name: Name of the game

        Returns:
            Tweet dictionary or None if parsing fails
        """
        # Extract tweet text
        content = self._extract_tweet_text(tweet_element)
        if not content:
            return None

        # Extract author info
        author_info = self._extract_author_info(tweet_element)

        # Extract timestamp
        posted_at = self._extract_timestamp(tweet_element)

        # Extract engagement metrics
        metrics = self._extract_engagement_metrics(tweet_element)

        # Classify post type
        post_type = classify_post_type(tweet_element, content)

        # Extract media URLs
        media_urls = extract_media_urls(tweet_element, post_type)

        # Extract hashtags and mentions
        hashtags = extract_hashtags(content)
        mentions = extract_mentions(content)

        # Generate post ID and URL
        post_id = self._generate_post_id(author_info.get('handle', ''), posted_at)
        post_url = self._construct_post_url(author_info.get('handle', ''), post_id)

        # Build tweet data dictionary
        tweet_data = {
            'post_id': post_id,
            'platform': self.PLATFORM_NAME,
            'game_name': game_name,
            'post_type': post_type,
            'content': content,
            'author': author_info.get('name', ''),
            'author_handle': author_info.get('handle', ''),
            'post_url': post_url,
            'posted_at': posted_at,
            'likes': metrics.get('likes', 0),
            'retweets': metrics.get('retweets', 0),
            'comments': metrics.get('replies', 0),
            'views': metrics.get('views', 0),
            'hashtags': ','.join(hashtags) if hashtags else None,
            'mentions': ','.join(mentions) if mentions else None,
            'media': media_urls  # This will be stored separately in post_media table
        }

        return tweet_data

    def _extract_tweet_text(self, tweet_element: Tag) -> str:
        """Extract tweet text content."""
        text_div = tweet_element.find('div', {'data-testid': 'tweetText'})
        if text_div:
            # Get all text, including from links
            return text_div.get_text(strip=True)
        return ""

    def _extract_author_info(self, tweet_element: Tag) -> Dict[str, str]:
        """Extract author name and handle."""
        author_info = {'name': '', 'handle': ''}

        # Find author link
        author_link = tweet_element.find('a', href=re.compile(r'^/\w+$'))
        if author_link:
            # Extract handle from href
            href = author_link.get('href', '')
            handle = href.lstrip('/')
            author_info['handle'] = handle

            # Extract display name
            name_span = author_link.find('span', class_=lambda x: x and 'css-901oao' in ' '.join(x))
            if name_span:
                author_info['name'] = name_span.get_text(strip=True)

        return author_info

    def _extract_timestamp(self, tweet_element: Tag) -> datetime:
        """
        Extract and parse tweet timestamp.

        Twitter shows relative times like "2h", "1d", etc.
        We convert these to absolute datetime objects.
        """
        time_element = tweet_element.find('time')
        if time_element and time_element.get('datetime'):
            # ISO format datetime
            dt_str = time_element['datetime']
            try:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            except:
                pass

        # Fallback: parse relative time from text
        if time_element:
            time_text = time_element.get_text(strip=True)
            return self._parse_relative_time(time_text)

        # Default to current time if no timestamp found
        return datetime.utcnow()

    def _parse_relative_time(self, time_str: str) -> datetime:
        """
        Parse relative time strings like "2h", "3d", "1m" to datetime.

        Args:
            time_str: Relative time string

        Returns:
            datetime object
        """
        now = datetime.utcnow()

        # Parse patterns like "2h", "3d", "5m", "1w"
        match = re.match(r'(\d+)([smhdw])', time_str.lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            if unit == 's':
                return now - timedelta(seconds=value)
            elif unit == 'm':
                return now - timedelta(minutes=value)
            elif unit == 'h':
                return now - timedelta(hours=value)
            elif unit == 'd':
                return now - timedelta(days=value)
            elif unit == 'w':
                return now - timedelta(weeks=value)

        # If parsing fails, return current time
        return now

    def _extract_engagement_metrics(self, tweet_element: Tag) -> Dict[str, int]:
        """
        Extract engagement metrics (likes, retweets, replies, views).

        Args:
            tweet_element: BeautifulSoup element for tweet

        Returns:
            Dictionary with engagement counts
        """
        metrics = {
            'replies': 0,
            'retweets': 0,
            'likes': 0,
            'views': 0
        }

        # Find engagement group
        engagement_group = tweet_element.find('div', {'role': 'group', 'aria-label': re.compile(r'Tweet engagement')})
        if not engagement_group:
            return metrics

        # Extract each metric type
        metric_map = {
            'reply': 'replies',
            'retweet': 'retweets',
            'like': 'likes',
            'views': 'views'
        }

        for testid, metric_name in metric_map.items():
            metric_div = engagement_group.find('div', {'data-testid': testid})
            if metric_div:
                # Find aria-label with count
                aria_label = metric_div.get('aria-label', '')
                count = self._parse_count_from_label(aria_label)
                metrics[metric_name] = count

        return metrics

    def _parse_count_from_label(self, label: str) -> int:
        """
        Parse count from aria-label like "5.8K Likes" or "1.2M Views".

        Args:
            label: Aria label string

        Returns:
            Integer count
        """
        # Extract number from label
        match = re.search(r'([\d.]+)([KMB]?)', label)
        if not match:
            return 0

        number_str = match.group(1)
        suffix = match.group(2)

        try:
            number = float(number_str)

            # Apply multiplier based on suffix
            if suffix == 'K':
                number *= 1_000
            elif suffix == 'M':
                number *= 1_000_000
            elif suffix == 'B':
                number *= 1_000_000_000

            return int(number)
        except ValueError:
            return 0

    def _generate_post_id(self, handle: str, posted_at: datetime) -> str:
        """
        Generate a unique post ID.

        Twitter doesn't expose tweet IDs easily in HTML,
        so we create a deterministic ID from handle and timestamp.

        Args:
            handle: Twitter handle
            posted_at: Post timestamp

        Returns:
            Unique post ID
        """
        timestamp_str = posted_at.strftime('%Y%m%d%H%M%S')
        return f"twitter_{handle}_{timestamp_str}"

    def _construct_post_url(self, handle: str, post_id: str) -> str:
        """
        Construct URL to the tweet.

        Note: Without real tweet ID, this is approximate.

        Args:
            handle: Twitter handle
            post_id: Post ID

        Returns:
            Tweet URL
        """
        return f"https://x.com/{handle}/status/{post_id}"


# Helper function for CLI usage
async def scrape_twitter_profile(
    profile_url: str,
    game_name: str,
    fallback_file: Optional[str] = None
) -> List[Dict]:
    """
    Convenience function to scrape a Twitter profile.

    Args:
        profile_url: Twitter profile URL
        game_name: Name of the game
        fallback_file: Optional fallback HTML file

    Returns:
        List of tweet dictionaries
    """
    scraper = TwitterScraper(headless=True)
    try:
        tweets = await scraper.scrape_profile(
            profile_url=profile_url,
            game_name=game_name,
            fallback_file=fallback_file
        )
        return tweets
    finally:
        await scraper.close_browser()
