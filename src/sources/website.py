"""
Website collector — scrapes news articles from gaming websites.

Wraps existing scraper.py + parser.py with per-site configuration.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from src.sources.base import BaseCollector, CollectedItem
from src.scraper import fetch_page
from src.parser import extract_full_article

logger = logging.getLogger(__name__)


@dataclass
class WebsiteConfig:
    """Per-site scraping configuration."""
    name: str
    listing_url: str
    base_url: str
    link_pattern: str           # regex pattern for article URLs
    exclude_patterns: List[str] = field(default_factory=list)


# Per-site configurations
WEBSITE_CONFIGS = {
    "pocketgamer": WebsiteConfig(
        name="pocketgamer",
        listing_url="https://www.pocketgamer.com/news/",
        base_url="https://www.pocketgamer.com",
        link_pattern=r"/news/.+",
        exclude_patterns=[r"\?page=", r"\.rss$"],
    ),
    "gamingonphone": WebsiteConfig(
        name="gamingonphone",
        listing_url="https://gamingonphone.com/news/",
        base_url="https://gamingonphone.com",
        link_pattern=r"/news/.+",
        exclude_patterns=[r"/news/$", r"\?page="],
    ),
    "droidgamers": WebsiteConfig(
        name="droidgamers",
        listing_url="https://www.droidgamers.com/",
        base_url="https://www.droidgamers.com",
        link_pattern=r"/\d{4}/\d{2}/.+",  # date-based URL pattern
        exclude_patterns=[r"/category/", r"/tag/"],
    ),
    "toucharcade": WebsiteConfig(
        name="toucharcade",
        listing_url="https://toucharcade.com/",
        base_url="https://toucharcade.com",
        link_pattern=r"/\d{4}/\d{2}/\d{2}/.+",
        exclude_patterns=[r"/category/", r"/tag/", r"#comment"],
    ),
    "pockettactics": WebsiteConfig(
        name="pockettactics",
        listing_url="https://www.pockettactics.com/",
        base_url="https://www.pockettactics.com",
        link_pattern=r"pockettactics\.com/.+",
        exclude_patterns=[r"/author/", r"/category/", r"/$"],
    ),
    "addictinggames": WebsiteConfig(
        name="addictinggames",
        listing_url="https://www.addictinggames.com/",
        base_url="https://www.addictinggames.com",
        link_pattern=r"addictinggames\.com/.+",
        exclude_patterns=[r"/category/", r"/tag/"],
    ),
    "minireview": WebsiteConfig(
        name="minireview",
        listing_url="https://minireview.io/",
        base_url="https://minireview.io",
        link_pattern=r"minireview\.io/.+",
        exclude_patterns=[r"/category/", r"/about", r"/contact"],
    ),
}


class WebsiteCollector(BaseCollector):
    """Collects articles from gaming news websites."""

    source_type = "website"

    def __init__(self, config: WebsiteConfig):
        self.config = config
        self.source_name = config.name

    def discover(self, limit: int = 20) -> List[str]:
        """Discover article URLs from the site's listing page."""
        try:
            html = fetch_page(self.config.listing_url)
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch listing: {e}")
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        article_urls = []

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if not href or href == '#':
                continue

            # Make absolute
            if href.startswith('/'):
                href = self.config.base_url + href
            elif not href.startswith('http'):
                continue

            # Must match link pattern
            if not re.search(self.config.link_pattern, href):
                continue

            # Must not match exclude patterns
            if any(re.search(ep, href) for ep in self.config.exclude_patterns):
                continue

            # Deduplicate
            href_clean = href.rstrip('/')
            if href_clean not in article_urls:
                article_urls.append(href_clean)

                if len(article_urls) >= limit:
                    break

        logger.info(f"[{self.source_name}] Discovered {len(article_urls)} article URLs")
        return article_urls

    def collect(self, url: str) -> Optional[CollectedItem]:
        """Fetch and parse a single article."""
        try:
            html = fetch_page(url)
            article = extract_full_article(html, url)

            if not article.get('title'):
                logger.warning(f"[{self.source_name}] No title extracted: {url}")
                return None

            return CollectedItem(
                url=url,
                title=article['title'],
                date=article.get('date'),
                author=article.get('author'),
                content=article.get('content'),
                image_url=article.get('image_url'),
                source_type='website',
                source_name=self.source_name,
            )

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to collect {url}: {e}")
            return None


def get_website_collectors() -> List[WebsiteCollector]:
    """Get collectors for all configured websites."""
    return [WebsiteCollector(config) for config in WEBSITE_CONFIGS.values()]
