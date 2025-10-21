"""
Web scraper module for SwipePads News Scraper.
Handles fetching and parsing of Pocket Gamer news articles.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from src.config import Config


def fetch_page(url: str, save_to: str = None) -> str:
    """
    Fetch HTML content from a URL.

    Args:
        url: The URL to fetch
        save_to: Optional path to save the HTML (relative to project root)

    Returns:
        str: The HTML content

    Raises:
        requests.RequestException: If the request fails
    """
    headers = {
        'User-Agent': Config.USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

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


if __name__ == '__main__':
    """
    Test the scraper by fetching Pocket Gamer news page.
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
        print(f"First 500 characters:")
        print("=" * 60)
        print(html[:500])
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
