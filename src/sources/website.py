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
    rss_url: Optional[str] = None       # if set, discover via RSS feed first
    user_agent: Optional[str] = None    # custom User-Agent (e.g. sites that 403 bots)


# Realistic browser UA for sites that block generic bot user agents (403s)
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Per-site configurations
# Removed (dead weight): addictinggames (game category pages, no news/dates),
# minireview (JS-rendered, 0 URLs discoverable without a headless browser).
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
    # TouchArcade returns 403 for generic bot UAs on HTML pages.
    # Fix: discover via their RSS feed + use a realistic browser User-Agent.
    # If both the feed and the browser UA stop working, discover() returns []
    # and the source is skipped gracefully.
    "toucharcade": WebsiteConfig(
        name="toucharcade",
        listing_url="https://toucharcade.com/",
        base_url="https://toucharcade.com",
        link_pattern=r"/\d{4}/\d{2}/\d{2}/.+",
        exclude_patterns=[r"/category/", r"/tag/", r"#comment"],
        rss_url="https://toucharcade.com/feed/",
        user_agent=BROWSER_USER_AGENT,
    ),
    # Pocket Tactics articles live at /{game-or-topic}/{article-slug}
    # (single-segment paths are category/hub pages — excluded via pattern).
    "pockettactics": WebsiteConfig(
        name="pockettactics",
        listing_url="https://www.pockettactics.com/",
        base_url="https://www.pockettactics.com",
        link_pattern=r"pockettactics\.com/[\w-]+/[\w-]+/?$",
        exclude_patterns=[
            r"/author/", r"/category/", r"/tag/", r"/page/",
            r"/wp-", r"\?", r"/reviews/$",
        ],
    ),
}


class WebsiteCollector(BaseCollector):
    """Collects articles from gaming news websites."""

    source_type = "website"

    def __init__(self, config: WebsiteConfig):
        self.config = config
        self.source_name = config.name
        self._rss_items: dict = {}  # url -> metadata from RSS (fallback for collect)

    def _headers(self) -> Optional[dict]:
        """Extra request headers (custom User-Agent) if configured."""
        if self.config.user_agent:
            return {'User-Agent': self.config.user_agent}
        return None

    def _discover_from_rss(self, limit: int) -> List[str]:
        """Discover article URLs from the site's RSS feed."""
        from bs4 import BeautifulSoup
        from email.utils import parsedate_to_datetime

        try:
            xml = fetch_page(self.config.rss_url, headers=self._headers())
        except Exception as e:
            logger.warning(f"[{self.source_name}] Failed to fetch RSS feed: {e}")
            return []

        soup = BeautifulSoup(xml, 'xml')
        urls = []
        for item in soup.find_all('item'):
            link_tag = item.find('link')
            if not link_tag or not link_tag.get_text(strip=True):
                continue
            url = link_tag.get_text(strip=True).rstrip('/')

            # Cache feed metadata so collect() can fall back to it
            # if the article page itself is blocked (e.g. 403).
            date_iso = None
            pub_date = item.find('pubDate')
            if pub_date and pub_date.get_text(strip=True):
                try:
                    date_iso = parsedate_to_datetime(
                        pub_date.get_text(strip=True)
                    ).isoformat()
                except (ValueError, TypeError):
                    pass

            title_tag = item.find('title')
            desc_tag = item.find('description')
            author_tag = item.find('creator') or item.find('author')
            self._rss_items[url] = {
                'title': title_tag.get_text(strip=True) if title_tag else None,
                'date': date_iso,
                'content': desc_tag.get_text(strip=True) if desc_tag else None,
                'author': author_tag.get_text(strip=True) if author_tag else None,
            }

            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                break

        logger.info(f"[{self.source_name}] Discovered {len(urls)} article URLs via RSS")
        return urls

    def discover(self, limit: int = 20) -> List[str]:
        """Discover article URLs from the site's RSS feed or listing page."""
        if self.config.rss_url:
            urls = self._discover_from_rss(limit)
            if urls:
                return urls
            logger.warning(
                f"[{self.source_name}] RSS discovery empty — falling back to HTML listing"
            )

        try:
            html = fetch_page(self.config.listing_url, headers=self._headers())
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

    def _collect_from_rss_cache(self, url: str) -> Optional[CollectedItem]:
        """Build item from cached RSS metadata (fallback when page fetch fails)."""
        meta = self._rss_items.get(url.rstrip('/'))
        if not meta or not meta.get('title'):
            return None

        logger.info(f"[{self.source_name}] Using RSS feed metadata for: {url}")
        return CollectedItem(
            url=url,
            title=meta['title'],
            date=meta.get('date'),
            author=meta.get('author'),
            content=meta.get('content'),
            image_url=None,
            source_type='website',
            source_name=self.source_name,
        )

    def collect(self, url: str) -> Optional[CollectedItem]:
        """Fetch and parse a single article."""
        try:
            html = fetch_page(url, headers=self._headers())
            article = extract_full_article(html, url)

            if not article.get('title'):
                logger.warning(f"[{self.source_name}] No title extracted: {url}")
                return self._collect_from_rss_cache(url)

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
            # Page blocked/unreachable — fall back to RSS metadata if available
            fallback = self._collect_from_rss_cache(url)
            if fallback:
                return fallback
            logger.error(f"[{self.source_name}] Failed to collect {url}: {e}")
            return None


def get_website_collectors() -> List[WebsiteCollector]:
    """Get collectors for all configured websites."""
    return [WebsiteCollector(config) for config in WEBSITE_CONFIGS.values()]
