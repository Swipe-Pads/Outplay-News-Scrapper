"""
Base collector abstraction for all content sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class CollectedItem:
    """Standardized item from any source."""
    url: str
    title: str
    source_type: str        # "website", "youtube", "reddit"
    source_name: str        # "pocketgamer", "iFerg", "AndroidGaming"
    date: Optional[str] = None
    author: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    content_id: Optional[str] = None  # video ID, post ID, etc.

    def to_dict(self) -> dict:
        return {
            'url': self.url,
            'title': self.title,
            'date': self.date,
            'author': self.author,
            'content': self.content,
            'image_url': self.image_url,
            'source_type': self.source_type,
            'source_name': self.source_name,
            'content_id': self.content_id,
        }


class BaseCollector(ABC):
    """Abstract base class for all content source collectors."""

    source_type: str = ""
    source_name: str = ""

    @abstractmethod
    def discover(self, limit: int = 20) -> List[str]:
        """
        Discover content identifiers (URLs, video IDs, post URLs).

        Args:
            limit: Max items to discover

        Returns:
            List of content identifiers
        """
        pass

    @abstractmethod
    def collect(self, identifier: str) -> Optional[CollectedItem]:
        """
        Fetch and parse a single content item.

        Args:
            identifier: URL, video ID, or post URL

        Returns:
            CollectedItem or None if collection failed
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.source_type}:{self.source_name}>"
