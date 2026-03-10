"""
YouTube Data API v3 client for gaming news scraper pipeline.

Provides methods for discovering gaming content through:
- Channel-specific video searches
- Game/topic trending video discovery

Uses YouTube Data API v3 with quota tracking to stay within daily limits.
Quota costs: search.list=100 units, videos.list=1 unit per video (10k daily limit).
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from dotenv import load_dotenv

from . import ScrapedContent


logger = logging.getLogger(__name__)
load_dotenv()


class YouTubeScraper:
    """YouTube Data API v3 client for discovering gaming content."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    # Default region code for relevance
    REGION_CODE = "US"

    def __init__(self):
        """Initialize YouTube scraper with API key from environment."""
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY must be set in environment")

        self.quota_used = 0  # Track API quota usage
        logger.info("YouTubeScraper initialized")

    def _make_request(
        self, endpoint: str, params: dict
    ) -> dict:
        """
        Make authenticated request to YouTube Data API.

        Args:
            endpoint: API endpoint name (e.g., "search", "videos").
            params: Query parameters including apiKey.

        Returns:
            dict: Parsed JSON response.

        Raises:
            requests.RequestException: If request fails.
            ValueError: If API returns an error.
        """
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = requests.get(
                url,
                params=params,
                timeout=15,
            )
            response.raise_for_status()

            data = response.json()

            # Check for API errors
            if "error" in data:
                error = data["error"]
                raise ValueError(f"YouTube API error: {error.get('message', str(error))}")

            return data

        except requests.RequestException as e:
            logger.error(f"YouTube API request failed: {e}")
            raise

    def _track_quota(self, endpoint: str, item_count: int = 1) -> None:
        """
        Track API quota usage.

        Quota costs:
        - search.list: 100 units per request
        - videos.list: 1 unit per item requested

        Args:
            endpoint: API endpoint used.
            item_count: Number of items requested (for videos.list).
        """
        if endpoint == "search":
            cost = 100
        elif endpoint == "videos":
            cost = item_count
        else:
            cost = 0

        self.quota_used += cost
        remaining = 10000 - self.quota_used
        logger.debug(
            f"API quota: {cost} units used ({self.quota_used}/{10000} total), "
            f"{remaining} remaining"
        )

    def _format_iso_datetime(self, dt: datetime) -> str:
        """
        Format datetime as ISO 8601 string for YouTube API.

        Args:
            dt: datetime object.

        Returns:
            str: ISO 8601 formatted datetime (RFC 3339).
        """
        return dt.isoformat() + "Z"

    def search_channel_videos(
        self,
        channel_id: str,
        max_age_days: int = 7,
        limit: int = 10,
    ) -> List[ScrapedContent]:
        """
        Search for recent videos from a specific YouTube channel.

        Args:
            channel_id: YouTube channel ID (e.g., "UCxxxxxxxxxxxxxx").
            max_age_days: Only include videos from last N days.
            limit: Maximum number of videos to retrieve (1-50).

        Returns:
            List[ScrapedContent]: Normalized video metadata.

        Raises:
            ValueError: If parameters are invalid.
            requests.RequestException: If API request fails.
        """
        if not channel_id or not isinstance(channel_id, str):
            raise ValueError("channel_id must be a non-empty string")

        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")

        if max_age_days < 1:
            raise ValueError("max_age_days must be at least 1")

        logger.info(f"Searching channel {channel_id} for recent videos (limit={limit})")

        # Calculate date cutoff
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        # search.list request
        search_params = {
            "apiKey": self.api_key,
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": min(limit, 50),
            "publishedAfter": self._format_iso_datetime(cutoff_date),
            "fields": "items(id/videoId,snippet(title,publishedAt,channelTitle))",
        }

        try:
            search_data = self._make_request("search", search_params)
            self._track_quota("search")
        except Exception as e:
            logger.error(f"Failed to search channel {channel_id}: {e}")
            return []

        items = search_data.get("items", [])
        logger.debug(f"Found {len(items)} videos from channel {channel_id}")

        if not items:
            return []

        # Extract video IDs
        video_ids = [item["id"]["videoId"] for item in items]

        # videos.list request for enriched metadata
        videos_params = {
            "apiKey": self.api_key,
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids),
            "fields": "items(id,snippet(title,description,publishedAt,thumbnails,channelTitle),statistics(viewCount))",
        }

        try:
            videos_data = self._make_request("videos", videos_params)
            self._track_quota("videos", len(video_ids))
        except Exception as e:
            logger.error(f"Failed to get video details: {e}")
            return []

        videos = videos_data.get("items", [])
        logger.debug(f"Retrieved metadata for {len(videos)} videos")

        scraped_content = []

        for video in videos:
            try:
                video_id = video["id"]
                snippet = video["snippet"]
                stats = video.get("statistics", {})

                title = snippet.get("title", "").strip()
                description = snippet.get("description", "").strip()
                channel_title = snippet.get("channelTitle", "Unknown")
                published_at = snippet.get("publishedAt", "")
                view_count = int(stats.get("viewCount", 0))

                # Extract thumbnail - prefer maxres, fall back to high
                thumbnails = snippet.get("thumbnails", {})
                thumbnail_url = (
                    thumbnails.get("maxres", {}).get("url")
                    or thumbnails.get("high", {}).get("url")
                    or thumbnails.get("default", {}).get("url")
                )

                # Also generate standard thumbnail URL
                image_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

                # Build ScrapedContent
                content: ScrapedContent = {
                    "source_type": "youtube",
                    "source_url": f"https://www.youtube.com/watch?v={video_id}",
                    "source_name": f"YouTube - {channel_title}",
                    "title": title,
                    "body": description,
                    "original_author": channel_title,
                    "youtube_video_id": video_id,
                    "image_url": image_url,
                    "score": view_count,
                    "content_type": "video",
                    "scraped_at": datetime.utcnow().isoformat() + "Z",
                    "source_published_at": published_at,
                }

                scraped_content.append(content)
                logger.debug(f"Scraped video: {title[:50]}... ({view_count} views)")

            except Exception as e:
                logger.warning(f"Error processing video: {e}")
                continue

        logger.info(
            f"Successfully scraped {len(scraped_content)} videos from channel {channel_id}"
        )
        return scraped_content

    def get_trending_game_videos(
        self,
        game_name: str,
        max_age_days: int = 7,
        limit: int = 10,
    ) -> List[ScrapedContent]:
        """
        Search for trending videos about a specific game.

        Uses relevance-based search to find popular gaming content about the
        specified game within a time window.

        Args:
            game_name: Game name to search for (e.g., "Call of Duty", "Valorant").
            max_age_days: Only include videos from last N days.
            limit: Maximum number of videos to retrieve (1-50).

        Returns:
            List[ScrapedContent]: Normalized video metadata.

        Raises:
            ValueError: If parameters are invalid.
            requests.RequestException: If API request fails.
        """
        if not game_name or not isinstance(game_name, str):
            raise ValueError("game_name must be a non-empty string")

        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")

        if max_age_days < 1:
            raise ValueError("max_age_days must be at least 1")

        logger.info(f"Searching for trending videos about '{game_name}' (limit={limit})")

        # Calculate date cutoff
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        # search.list request
        search_params = {
            "apiKey": self.api_key,
            "part": "snippet",
            "q": game_name,
            "type": "video",
            "order": "relevance",
            "maxResults": min(limit, 50),
            "publishedAfter": self._format_iso_datetime(cutoff_date),
            "relevanceLanguage": "en",
            "regionCode": self.REGION_CODE,
            "fields": "items(id/videoId,snippet(title,publishedAt,channelTitle))",
        }

        try:
            search_data = self._make_request("search", search_params)
            self._track_quota("search")
        except Exception as e:
            logger.error(f"Failed to search for '{game_name}': {e}")
            return []

        items = search_data.get("items", [])
        logger.debug(f"Found {len(items)} videos matching '{game_name}'")

        if not items:
            return []

        # Extract video IDs
        video_ids = [item["id"]["videoId"] for item in items]

        # videos.list request for enriched metadata
        videos_params = {
            "apiKey": self.api_key,
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids),
            "fields": "items(id,snippet(title,description,publishedAt,thumbnails,channelTitle),statistics(viewCount))",
        }

        try:
            videos_data = self._make_request("videos", videos_params)
            self._track_quota("videos", len(video_ids))
        except Exception as e:
            logger.error(f"Failed to get video details for '{game_name}': {e}")
            return []

        videos = videos_data.get("items", [])
        logger.debug(f"Retrieved metadata for {len(videos)} videos")

        scraped_content = []

        for video in videos:
            try:
                video_id = video["id"]
                snippet = video["snippet"]
                stats = video.get("statistics", {})

                title = snippet.get("title", "").strip()
                description = snippet.get("description", "").strip()
                channel_title = snippet.get("channelTitle", "Unknown")
                published_at = snippet.get("publishedAt", "")
                view_count = int(stats.get("viewCount", 0))

                # Generate thumbnail URL
                image_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

                # Build ScrapedContent
                content: ScrapedContent = {
                    "source_type": "youtube",
                    "source_url": f"https://www.youtube.com/watch?v={video_id}",
                    "source_name": f"YouTube - {channel_title}",
                    "title": title,
                    "body": description,
                    "original_author": channel_title,
                    "youtube_video_id": video_id,
                    "image_url": image_url,
                    "score": view_count,
                    "content_type": "video",
                    "scraped_at": datetime.utcnow().isoformat() + "Z",
                    "source_published_at": published_at,
                }

                scraped_content.append(content)
                logger.debug(f"Scraped video: {title[:50]}... ({view_count} views)")

            except Exception as e:
                logger.warning(f"Error processing video: {e}")
                continue

        logger.info(
            f"Successfully scraped {len(scraped_content)} trending videos for '{game_name}'"
        )
        return scraped_content


def main():
    """Standalone testing of YouTube scraper."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        scraper = YouTubeScraper()

        # Example: search for trending gaming videos
        videos = scraper.get_trending_game_videos(
            game_name="Call of Duty",
            max_age_days=7,
            limit=5,
        )

        for video in videos:
            print(f"\n{video['source_name']}")
            print(f"Title: {video['title']}")
            print(f"Views: {video['score']:,}")
            print(f"URL: {video['source_url']}")
            print(f"Published: {video['source_published_at']}")

        print(f"\nTotal API quota used: {scraper.quota_used}/10000")

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    main()
