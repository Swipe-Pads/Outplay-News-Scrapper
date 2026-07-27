"""
Source registry — central hub for all content sources.
"""

import logging
from typing import List, Optional

from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

# Lazy-loaded source list
_sources: Optional[List[BaseCollector]] = None


def _load_sources() -> List[BaseCollector]:
    """Load all source collectors."""
    sources = []

    # Websites
    try:
        from src.sources.website import get_website_collectors
        sources.extend(get_website_collectors())
    except Exception as e:
        logger.warning(f"Failed to load website collectors: {e}")

    # YouTube
    try:
        from src.sources.youtube import get_youtube_collectors
        sources.extend(get_youtube_collectors())
    except Exception as e:
        logger.warning(f"Failed to load YouTube collectors: {e}")

    # Reddit
    try:
        from src.sources.reddit import get_reddit_collectors
        sources.extend(get_reddit_collectors())
    except Exception as e:
        logger.warning(f"Failed to load Reddit collectors: {e}")

    # Newsletters (news.outplay.game inbox)
    try:
        from src.sources.newsletter import get_newsletter_collectors
        sources.extend(get_newsletter_collectors())
    except Exception as e:
        logger.warning(f"Failed to load newsletter collectors: {e}")

    return sources


def get_all_sources() -> List[BaseCollector]:
    """Get all registered source collectors."""
    global _sources
    if _sources is None:
        _sources = _load_sources()
    return _sources


# Alias
SOURCES = property(lambda self: get_all_sources())


def get_sources(
    source_type: str = None,
    source_name: str = None
) -> List[BaseCollector]:
    """
    Get sources filtered by type and/or name.

    Args:
        source_type: "website", "youtube", "reddit", or "newsletter"
        source_name: Specific source name (e.g., "pocketgamer", "iFerg")

    Returns:
        Filtered list of collectors
    """
    sources = get_all_sources()

    if source_type:
        sources = [s for s in sources if s.source_type == source_type]

    if source_name:
        sources = [s for s in sources if s.source_name == source_name]

    return sources


def get_source(source_name: str) -> Optional[BaseCollector]:
    """Get a single source by name."""
    matches = get_sources(source_name=source_name)
    return matches[0] if matches else None


def list_sources() -> List[dict]:
    """List all sources with their type and name."""
    return [
        {
            'type': s.source_type,
            'name': s.source_name,
            'collector': s.__class__.__name__,
        }
        for s in get_all_sources()
    ]
