"""
Web scraper module for SwipePads News Scraper.
Handles fetching and parsing of Pocket Gamer news articles.
"""

from pathlib import Path

import requests
from bs4 import BeautifulSoup
from typing import List
from src.config import Config


def fetch_page(url: str, save_to: str = None, headers: dict = None) -> str:
    """
    Fetch HTML content from a URL.

    Args:
        url: The URL to fetch
        save_to: Optional path to save the HTML (relative to project root)
        headers: Optional extra headers (e.g. custom User-Agent) merged over defaults

    Returns:
        str: The HTML content

    Raises:
        requests.RequestException: If the request fails
    """
    request_headers = {
        'User-Agent': Config.USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    if headers:
        request_headers.update(headers)
    headers = request_headers

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        html_content = response.text

        # Save to file if requested
        if save_to:
            project_root = Path(__file__).parent.parent
            save_path = project_root / save_to
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Use Path.write_text to ensure proper encoding
            save_path.write_text(html_content, encoding='utf-8')

            print(f"Saved HTML to: {save_path}")

        return html_content

    except requests.Timeout:
        raise requests.RequestException(f"Timeout while fetching {url}")
    except requests.HTTPError as e:
        raise requests.RequestException(f"HTTP error {e.response.status_code} while fetching {url}")
    except requests.RequestException as e:
        raise requests.RequestException(f"Error fetching {url}: {e}")


def parse_article_links(html: str, limit: int = None) -> List[str]:
    """
    Parse article URLs from Pocket Gamer news listing page.

    Args:
        html: The HTML content of the news listing page
        limit: Optional limit on number of URLs to return

    Returns:
        List[str]: List of article URLs
    """
    soup = BeautifulSoup(html, 'lxml')
    article_urls = []

    # Find all links
    all_links = soup.find_all('a', href=True)

    for link in all_links:
        href = link.get('href', '')

        # Skip empty or invalid hrefs
        if not href or href == '#':
            continue

        # Make absolute URLs
        if href.startswith('/'):
            href = f'https://www.pocketgamer.com{href}'
        elif not href.startswith('http'):
            continue

        # Only include article URLs
        if '/news/' in href:
            # Exclude: main news page, RSS feeds, page navigation
            if (href.rstrip('/') != 'https://www.pocketgamer.com/news' and
                not href.endswith('.rss') and
                '?page=' not in href and
                href not in article_urls):
                article_urls.append(href)

                if limit and len(article_urls) >= limit:
                    return article_urls

    return article_urls


if __name__ == '__main__':
    """
    Test the scraper by fetching and parsing Pocket Gamer news page.
    """
    import sys

    url = 'https://www.pocketgamer.com/news/'

    print(f"Fetching: {url}")
    print(f"User-Agent: {Config.USER_AGENT}")
    print()

    try:
        html = fetch_page(url, save_to='data/homepage.html')

        print(f"✅ Successfully fetched {len(html)} characters")
        print(f"✅ Saved to: data/homepage.html")
        print()

        # Parse article links
        print("Parsing article links...")
        article_urls = parse_article_links(html, limit=5)

        print(f"✅ Found {len(article_urls)} article URLs")
        print()
        print("First 5 article URLs:")
        print("=" * 60)
        for i, url in enumerate(article_urls[:5], 1):
            print(f"{i}. {url}")
        print("=" * 60)
        print()

        # Fetch a single article to verify
        if article_urls:
            print(f"Fetching sample article...")
            article_url = article_urls[0]
            print(f"URL: {article_url}")
            article_html = fetch_page(article_url, save_to='data/article_sample.html')
            print(f"✅ Fetched {len(article_html)} characters")
            print(f"✅ Saved to: data/article_sample.html")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
