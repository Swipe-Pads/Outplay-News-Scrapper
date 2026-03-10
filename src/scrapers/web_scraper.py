"""
Web scraper for gaming news blogs and official sites.

Wraps the existing scraper.py and parser.py modules to provide a standardized
ScrapedContent interface compatible with the multi-source pipeline.

Supports scraping from any blog/news site by combining generic HTTP fetching
with BeautifulSoup-based content extraction.
"""

import logging
import re
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from . import ScrapedContent

logger = logging.getLogger(__name__)
load_dotenv()

# Default user agent
USER_AGENT = "OutplayNewsScraper/1.0"
REQUEST_TIMEOUT = 30


class WebScraper:
    """Generic web scraper for gaming news blogs and official sites."""

    def __init__(self, user_agent: str = USER_AGENT, rate_limit: float = 2.0):
        """
        Initialize web scraper.

        Args:
            user_agent: User-Agent header for HTTP requests.
            rate_limit: Minimum seconds between requests to same domain.
        """
        self.user_agent = user_agent
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
        })
        logger.info("WebScraper initialized")

    def _rate_limit_wait(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL.

        Args:
            url: URL to fetch.

        Returns:
            HTML content string, or None on failure.
        """
        self._rate_limit_wait()
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def extract_article_links(
        self,
        listing_url: str,
        link_pattern: str = r"/news/",
        limit: int = 20,
    ) -> List[str]:
        """
        Extract article URLs from a listing/index page.

        Args:
            listing_url: URL of the listing page.
            link_pattern: Regex pattern to match article links.
            limit: Maximum number of links to extract.

        Returns:
            List of absolute article URLs.
        """
        html = self.fetch_page(listing_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        base_domain = urlparse(listing_url).scheme + "://" + urlparse(listing_url).netloc

        seen = set()
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Make absolute
            abs_url = urljoin(base_domain, href)

            # Filter by pattern
            if not re.search(link_pattern, abs_url):
                continue

            # Skip pagination, RSS, etc.
            if any(skip in abs_url for skip in ["?page=", "/rss", "/feed", "/tag/", "/category/"]):
                continue

            # Deduplicate
            if abs_url in seen:
                continue
            seen.add(abs_url)
            links.append(abs_url)

            if len(links) >= limit:
                break

        logger.info(f"Extracted {len(links)} article links from {listing_url}")
        return links

    def extract_article(self, url: str) -> Optional[ScrapedContent]:
        """
        Extract article content from a single page.

        Uses multi-strategy extraction:
        1. JSON-LD structured data
        2. Open Graph / Twitter meta tags
        3. HTML element parsing

        Args:
            url: Article URL.

        Returns:
            ScrapedContent dict, or None on failure.
        """
        html = self.fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        domain = urlparse(url).netloc

        # --- Extract metadata ---
        title = self._extract_title(soup)
        content = self._extract_content(soup)
        author = self._extract_author(soup)
        published_date = self._extract_date(soup)
        image_url = self._extract_image(soup, url)

        if not title:
            logger.warning(f"No title found for {url}")
            return None

        return {
            "source_type": "web",
            "source_url": url,
            "source_name": domain,
            "title": title,
            "body": content or "",
            "original_author": author or "Unknown",
            "image_url": image_url or "",
            "content_type": "news",
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "source_published_at": published_date or "",
            "score": 0,
        }

    def scrape_listing(
        self,
        listing_url: str,
        link_pattern: str = r"/news/",
        limit: int = 20,
        source_name: str = None,
        game_slug: str = None,
    ) -> List[ScrapedContent]:
        """
        Scrape multiple articles from a listing page.

        Args:
            listing_url: URL of the article listing.
            link_pattern: Regex to filter article links.
            limit: Max articles to scrape.
            source_name: Override source name.
            game_slug: Associated game slug.

        Returns:
            List of ScrapedContent dicts.
        """
        links = self.extract_article_links(listing_url, link_pattern, limit)
        results = []

        for i, link in enumerate(links):
            logger.info(f"[{i+1}/{len(links)}] Scraping: {link}")
            article = self.extract_article(link)
            if article:
                if source_name:
                    article["source_name"] = source_name
                if game_slug:
                    article["game_slug"] = game_slug
                results.append(article)

        logger.info(f"Scraped {len(results)}/{len(links)} articles from {listing_url}")
        return results

    # --- Private extraction methods ---

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from JSON-LD, OG, or HTML."""
        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if "headline" in data:
                    return data["headline"].strip()
            except Exception:
                pass

        # Open Graph
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()

        # HTML
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        return None

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article body text."""
        # Try article/main content containers
        for selector in ["article", "[class*='article-body']", "[class*='post-content']",
                         "[class*='entry-content']", "main", "[role='main']"]:
            container = soup.select_one(selector)
            if container:
                paragraphs = container.find_all("p")
                text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
                if text and len(text) > 100:
                    return text

        # Fallback: all paragraphs
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
        return text if text else None

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author name."""
        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                author = data.get("author")
                if isinstance(author, dict):
                    return author.get("name")
                if isinstance(author, str):
                    return author
            except Exception:
                pass

        # Meta tags
        for meta in soup.find_all("meta", attrs={"name": "author"}):
            if meta.get("content"):
                return meta["content"].strip()

        # Byline classes
        for cls in ["byline", "author", "post-author"]:
            el = soup.find(class_=re.compile(cls, re.I))
            if el:
                return el.get_text(strip=True)

        return None

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract publication date."""
        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                for field in ["datePublished", "dateCreated"]:
                    if field in data:
                        return data[field]
            except Exception:
                pass

        # Meta tags
        for prop in ["article:published_time", "og:published_time"]:
            meta = soup.find("meta", property=prop)
            if meta and meta.get("content"):
                return meta["content"]

        # Time element
        time_el = soup.find("time", datetime=True)
        if time_el:
            return time_el["datetime"]

        return None

    def _extract_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract primary image URL."""
        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                img = data.get("image")
                if isinstance(img, str):
                    return urljoin(base_url, img)
                if isinstance(img, dict):
                    return urljoin(base_url, img.get("url", ""))
                if isinstance(img, list) and img:
                    return urljoin(base_url, img[0] if isinstance(img[0], str) else img[0].get("url", ""))
            except Exception:
                pass

        # OG image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return urljoin(base_url, og["content"])

        # Twitter image
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            return urljoin(base_url, tw["content"])

        return None


def main():
    """Standalone testing of web scraper."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    scraper = WebScraper()
    articles = scraper.scrape_listing(
        listing_url="https://www.pocketgamer.com/news/",
        link_pattern=r"/news/",
        limit=3,
        source_name="Pocket Gamer",
    )

    for a in articles:
        print(f"\nTitle: {a['title']}")
        print(f"Author: {a['original_author']}")
        print(f"URL: {a['source_url']}")
        print(f"Body length: {len(a.get('body', ''))} chars")


if __name__ == "__main__":
    main()
