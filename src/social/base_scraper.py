"""
Base scraper class for social media platforms using Playwright.
Includes fallback support for environments with HTTP restrictions.
"""

import asyncio
from pathlib import Path
from typing import Optional
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout


class SocialScraperError(Exception):
    """Base exception for social media scraping."""
    pass


class BaseSocialScraper(ABC):
    """
    Abstract base class for social media scrapers.

    Provides common functionality for Playwright-based scraping
    with automatic fallback to local HTML files when live scraping fails.
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize the social scraper.

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for page loads (milliseconds)
        """
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None

    async def init_browser(self):
        """Initialize Playwright browser."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=self.headless)
            print("✅ Browser initialized")
        except Exception as e:
            print(f"⚠️  Failed to initialize browser: {e}")
            print("   Will use fallback HTML files for testing")

    async def close_browser(self):
        """Close Playwright browser."""
        if self.browser:
            await self.browser.close()
            self.browser = None

    async def fetch_page(
        self,
        url: str,
        fallback_file: Optional[str] = None,
        wait_for: Optional[str] = None
    ) -> str:
        """
        Fetch HTML content from a URL or fallback file.

        Args:
            url: URL to fetch
            fallback_file: Path to local HTML file (fallback)
            wait_for: CSS selector to wait for (optional)

        Returns:
            HTML content as string

        Raises:
            SocialScraperError: If fetch fails and no fallback available
        """
        # Try live scraping first
        try:
            if not self.browser:
                await self.init_browser()

            # If browser failed to initialize, immediately use fallback
            if not self.browser:
                if fallback_file:
                    print(f"   Browser not available, using fallback file: {fallback_file}")
                    return self._load_fallback_file(fallback_file)
                else:
                    raise SocialScraperError("Browser not available and no fallback file provided")

            print(f"🔍 Fetching: {url}")

            context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US'
            )

            page = await context.new_page()
            response = await page.goto(url, wait_until='networkidle', timeout=self.timeout)

            if response and response.status == 200:
                # Wait for specific element if requested
                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, timeout=10000)
                    except PlaywrightTimeout:
                        print(f"⚠️  Timeout waiting for selector: {wait_for}")

                html_content = await page.content()
                await context.close()

                print(f"✅ Fetched {len(html_content):,} bytes from {url}")
                return html_content
            else:
                status = response.status if response else "No response"
                raise SocialScraperError(f"HTTP {status}")

        except Exception as e:
            print(f"⚠️  Live scraping failed: {type(e).__name__}: {str(e)}")

            # Fall back to local HTML file
            if fallback_file:
                print(f"   Using fallback file: {fallback_file}")
                return self._load_fallback_file(fallback_file)
            else:
                raise SocialScraperError(f"Failed to fetch {url} and no fallback available") from e

    def _load_fallback_file(self, fallback_path: str) -> str:
        """
        Load HTML content from a local file.

        Args:
            fallback_path: Path to local HTML file

        Returns:
            HTML content from file

        Raises:
            FileNotFoundError: If fallback file doesn't exist
        """
        try:
            # Support both absolute and relative paths
            file_path = Path(fallback_path)
            if not file_path.is_absolute():
                # Relative to project root
                project_root = Path(__file__).parent.parent.parent
                file_path = project_root / fallback_path

            if not file_path.exists():
                raise FileNotFoundError(f"Fallback file not found: {file_path}")

            html_content = file_path.read_text(encoding='utf-8')
            print(f"✅ Loaded {len(html_content):,} bytes from fallback file")
            return html_content

        except Exception as e:
            raise SocialScraperError(f"Failed to load fallback file: {e}") from e

    @abstractmethod
    async def scrape_profile(self, profile_url: str, game_name: str) -> list:
        """
        Scrape posts from a social media profile.

        Args:
            profile_url: URL of the profile to scrape
            game_name: Name of the game (for database storage)

        Returns:
            List of parsed post dictionaries

        Note:
            Must be implemented by platform-specific subclasses.
        """
        pass

    @abstractmethod
    def parse_posts(self, html_content: str, game_name: str) -> list:
        """
        Parse posts from HTML content.

        Args:
            html_content: Raw HTML content
            game_name: Name of the game

        Returns:
            List of parsed post dictionaries

        Note:
            Must be implemented by platform-specific subclasses.
        """
        pass
