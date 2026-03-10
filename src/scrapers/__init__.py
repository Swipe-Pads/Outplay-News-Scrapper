"""
Scrapers module for gaming news pipeline.

Provides standardized interfaces for extracting gaming content from multiple sources:
- Reddit communities
- YouTube channels
- Official blogs
- Web sources

All scrapers output normalized ScrapedContent dictionaries for consistent downstream processing.
"""

from typing import TypedDict, Optional, List


class ScrapedContent(TypedDict, total=False):
    """
    Standardized output format from all scrapers.

    This TypedDict allows optional fields (total=False) to accommodate different
    source types. For example, Reddit posts won't have video_url, while YouTube
    videos will have youtube_video_id.

    All fields are optional except source_url, which is required for deduplication
    and tracking across the pipeline.
    """
    source_type: str            # "reddit" | "youtube" | "web" | "official_blog"
    source_url: str             # Original URL (REQUIRED - used for dedup)
    source_name: str            # Human-readable source (e.g. "Reddit r/CoDMCompetitive")
    title: str                  # Raw title from source
    body: str                   # Raw content/body text
    original_author: str        # Original poster/author/channel name
    image_url: str              # Best available image URL
    video_url: str              # YouTube/Twitch embed URL (if applicable)
    youtube_video_id: str       # For thumbnail extraction
    game_slug: str              # Maps to Game entity (e.g. "cod-mobile", "valorant")
    content_type: str           # "news" | "video" | "community" | "update" (initial guess)
    scraped_at: str             # ISO 8601 timestamp when scraped
    source_published_at: str    # ISO 8601 timestamp when original was published
    score: int                  # Engagement metric (upvotes, views, retweets, etc.)


__all__ = [
    "ScrapedContent",
]
