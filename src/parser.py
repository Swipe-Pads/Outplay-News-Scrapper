"""
Article HTML parser for extracting metadata and content.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import re
from typing import Dict, Optional
from bs4 import BeautifulSoup


def parse_article_metadata(html: str) -> Dict[str, Optional[str]]:
    """
    Extract article metadata (title, date, author) from HTML.

    Args:
        html: Article HTML content

    Returns:
        Dictionary with keys: title, date, author
        Missing fields will be None

    Example:
        >>> html = open('data/article_sample.html').read()
        >>> meta = parse_article_metadata(html)
        >>> print(meta['title'])
        'Nominations are now open for the 12th Pocket Gamer Awards'
    """
    soup = BeautifulSoup(html, 'lxml')

    metadata = {
        'title': None,
        'date': None,
        'author': None,
    }

    # Strategy 1: Try JSON-LD structured data (most reliable)
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)

            # JSON-LD can be an array of objects
            if isinstance(data, list):
                # Look for NewsArticle type
                for item in data:
                    if item.get('@type') == 'NewsArticle':
                        data = item
                        break

            # Extract from NewsArticle structured data
            if isinstance(data, dict) and data.get('@type') == 'NewsArticle':
                if 'headline' in data:
                    metadata['title'] = data['headline']

                if 'datePublished' in data:
                    metadata['date'] = data['datePublished']

                if 'author' in data:
                    author_data = data['author']
                    if isinstance(author_data, dict) and 'name' in author_data:
                        metadata['author'] = author_data['name']
                    elif isinstance(author_data, str):
                        metadata['author'] = author_data

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    # Strategy 2: Fallback to HTML elements if JSON-LD failed
    if not metadata['title']:
        # Try h1 tag
        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text(strip=True)
        else:
            # Last resort: meta og:title
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                metadata['title'] = og_title['content']

    if not metadata['date']:
        # Try time element with datetime attribute
        time_elem = soup.find('time', datetime=True)
        if time_elem:
            metadata['date'] = time_elem['datetime']

    if not metadata['author']:
        # Try byline class/element (common pattern)
        byline = soup.find(class_=re.compile('byline|author', re.I))
        if byline:
            # Extract text, excluding any nested time elements
            author_text = byline.get_text(strip=True)
            # Clean up common prefixes
            author_text = re.sub(r'^(by|author):?\s*', '', author_text, flags=re.I)
            if author_text:
                metadata['author'] = author_text

    return metadata


def parse_article_content(html: str) -> str:
    """
    Extract main article content (paragraphs) from HTML.

    Args:
        html: Article HTML content

    Returns:
        Article content as clean text (no HTML tags)
        Returns empty string if no content found

    Example:
        >>> html = open('data/article_sample.html').read()
        >>> content = parse_article_content(html)
        >>> print(len(content))
        2500
    """
    soup = BeautifulSoup(html, 'lxml')

    content_text = ""

    # Strategy 1: Look for common article content containers
    # Try multiple selectors in priority order
    content_selectors = [
        {'class': re.compile('body-copy|article-body|entry-content|post-content', re.I)},
        {'class': 'article'},
        {'itemprop': 'articleBody'},
    ]

    content_container = None
    for selector in content_selectors:
        content_container = soup.find('div', selector)
        if content_container:
            break

    # Strategy 2: If no container found, try to find article tag
    if not content_container:
        content_container = soup.find('article')

    if content_container:
        # Extract all paragraphs
        paragraphs = content_container.find_all('p')

        # Clean and join paragraphs
        clean_paragraphs = []
        for p in paragraphs:
            # Get text, stripping HTML tags
            text = p.get_text(separator=' ', strip=True)

            # Skip empty paragraphs or very short ones (likely ads/cruft)
            if len(text) < 20:
                continue

            # Skip if looks like advertisement or related content
            lower_text = text.lower()
            if any(skip in lower_text for skip in ['advertisement', 'sponsored', 'read more:', 'related:']):
                continue

            clean_paragraphs.append(text)

        # Join with double newlines for readability
        content_text = '\n\n'.join(clean_paragraphs)

    return content_text


def parse_article_image(html: str) -> Optional[str]:
    """
    Extract main article image URL from HTML.

    Args:
        html: Article HTML content

    Returns:
        Image URL as string, or None if not found

    Example:
        >>> html = open('data/article_sample.html').read()
        >>> img_url = parse_article_image(html)
        >>> print(img_url)
        'https://media.pocketgamer.com/artwork/...'
    """
    soup = BeautifulSoup(html, 'lxml')

    image_url = None

    # Strategy 1: Try JSON-LD structured data (most reliable)
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)

            # JSON-LD can be an array of objects
            if isinstance(data, list):
                for item in data:
                    if item.get('@type') == 'NewsArticle':
                        data = item
                        break

            # Extract from NewsArticle structured data
            if isinstance(data, dict) and data.get('@type') == 'NewsArticle':
                if 'image' in data:
                    image_data = data['image']
                    if isinstance(image_data, dict) and 'url' in image_data:
                        image_url = image_data['url']
                    elif isinstance(image_data, str):
                        image_url = image_data

                    if image_url:
                        break

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    # Strategy 2: Try Open Graph meta tag
    if not image_url:
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content']

    # Strategy 3: Try Twitter meta tag
    if not image_url:
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            image_url = twitter_image['content']

    # Strategy 4: Try to find main article image (figure.lead img, article img, etc.)
    if not image_url:
        # Look for common patterns
        img_selectors = [
            soup.find('figure', class_=re.compile('lead|hero|featured', re.I)),
            soup.find('div', class_=re.compile('article.*image|featured.*image', re.I)),
            soup.find('article')
        ]

        for container in img_selectors:
            if container:
                img_tag = container.find('img')
                if img_tag:
                    # Try src, then data-src (lazy loading)
                    image_url = img_tag.get('src') or img_tag.get('data-src')
                    if image_url:
                        break

    # Validate and normalize URL
    if image_url:
        # Make relative URLs absolute
        if image_url.startswith('/'):
            # Extract base URL from article (need to get it from somewhere)
            # For now, return as-is - caller should handle this
            pass
        elif not image_url.startswith('http'):
            # Invalid URL
            return None

    return image_url


if __name__ == '__main__':
    """
    Test the parser with sample article HTML.
    """
    import sys

    article_path = Path('data/article_sample.html')

    if not article_path.exists():
        print(f"❌ Sample article not found: {article_path}")
        print("Run: python -m src.scraper")
        sys.exit(1)

    print(f"Reading: {article_path}")
    html = article_path.read_text(encoding='utf-8')
    print(f"✅ Loaded {len(html)} characters")
    print()

    print("Extracting metadata...")
    metadata = parse_article_metadata(html)

    print("=" * 60)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    print("=" * 60)
    print()

    # Validate results
    errors = []
    if not metadata['title']:
        errors.append("❌ Title not extracted")
    else:
        print(f"✅ Title: {metadata['title']}")

    if not metadata['date']:
        errors.append("❌ Date not extracted")
    else:
        print(f"✅ Date: {metadata['date']}")

    if not metadata['author']:
        print("⚠️  Author: None (may be missing from article)")
    else:
        print(f"✅ Author: {metadata['author']}")

    if errors:
        print()
        for error in errors:
            print(error)
        sys.exit(1)
    else:
        print()
        print("✅ All metadata extracted successfully!")

    print()
    print("=" * 60)
    print("Extracting content...")
    print("=" * 60)
    print()

    content = parse_article_content(html)

    if not content:
        print("❌ No content extracted")
        sys.exit(1)

    print(f"✅ Extracted {len(content)} characters of content")
    print()
    print("First 200 characters:")
    print("-" * 60)
    print(content[:200])
    print("-" * 60)
    print()

    # Check for HTML tags (shouldn't have any)
    if '<' in content and '>' in content:
        print("⚠️  Warning: Content contains HTML tags")
    else:
        print("✅ Content is clean text (no HTML tags)")

    print()
    print("=" * 60)
    print("Extracting image URL...")
    print("=" * 60)
    print()

    image_url = parse_article_image(html)

    if not image_url:
        print("❌ No image URL found")
        sys.exit(1)

    print(f"✅ Image URL: {image_url}")
    print()

    # Validate URL format
    if not image_url.startswith('http'):
        print("⚠️  Warning: Image URL is not absolute")
    else:
        print("✅ Image URL is absolute")

    print()
    print("✅ All parsing tests passed!")
