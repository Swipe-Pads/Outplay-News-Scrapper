"""
Article HTML parser for extracting metadata and content.
"""

import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from bs4 import BeautifulSoup


def _parse_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    """Extract NewsArticle JSON-LD data from soup. Returns dict or None."""
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('@type') == 'NewsArticle':
                        return item
            elif isinstance(data, dict) and data.get('@type') == 'NewsArticle':
                return data
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return None


def parse_article_metadata(html: str = None, soup: BeautifulSoup = None, json_ld: dict = None) -> Dict[str, Optional[str]]:
    """
    Extract article metadata (title, date, author) from HTML.

    Args:
        html: Article HTML content (used if soup not provided)
        soup: Pre-parsed BeautifulSoup object
        json_ld: Pre-parsed JSON-LD data

    Returns:
        Dictionary with keys: title, date, author
    """
    if soup is None:
        soup = BeautifulSoup(html, 'lxml')
    if json_ld is None:
        json_ld = _parse_json_ld(soup)

    metadata = {'title': None, 'date': None, 'author': None}

    # Strategy 1: JSON-LD structured data (most reliable)
    if json_ld:
        if 'headline' in json_ld:
            metadata['title'] = json_ld['headline']
        if 'datePublished' in json_ld:
            metadata['date'] = json_ld['datePublished']
        if 'author' in json_ld:
            author_data = json_ld['author']
            if isinstance(author_data, dict) and 'name' in author_data:
                metadata['author'] = author_data['name']
            elif isinstance(author_data, str):
                metadata['author'] = author_data

    # Strategy 2: Fallback to HTML elements
    if not metadata['title']:
        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text(strip=True)
        else:
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                metadata['title'] = og_title['content']

    if not metadata['date']:
        time_elem = soup.find('time', datetime=True)
        if time_elem:
            metadata['date'] = time_elem['datetime']

    if not metadata['author']:
        byline = soup.find(class_=re.compile('byline|author', re.I))
        if byline:
            author_text = byline.get_text(strip=True)
            author_text = re.sub(r'^(by|author):?\s*', '', author_text, flags=re.I)
            if author_text:
                metadata['author'] = author_text

    return metadata


def parse_article_content(html: str = None, soup: BeautifulSoup = None) -> str:
    """
    Extract main article content (paragraphs) from HTML.

    Args:
        html: Article HTML content (used if soup not provided)
        soup: Pre-parsed BeautifulSoup object

    Returns:
        Article content as clean text
    """
    if soup is None:
        soup = BeautifulSoup(html, 'lxml')

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

    if not content_container:
        content_container = soup.find('article')

    if not content_container:
        return ""

    clean_paragraphs = []
    for p in content_container.find_all('p'):
        text = p.get_text(separator=' ', strip=True)
        if len(text) < 20:
            continue
        lower_text = text.lower()
        if any(skip in lower_text for skip in ['advertisement', 'sponsored', 'read more:', 'related:']):
            continue
        clean_paragraphs.append(text)

    return '\n\n'.join(clean_paragraphs)


def parse_article_image(html: str = None, soup: BeautifulSoup = None, json_ld: dict = None) -> Optional[str]:
    """
    Extract main article image URL from HTML.

    Args:
        html: Article HTML content (used if soup not provided)
        soup: Pre-parsed BeautifulSoup object
        json_ld: Pre-parsed JSON-LD data

    Returns:
        Image URL as string, or None
    """
    if soup is None:
        soup = BeautifulSoup(html, 'lxml')
    if json_ld is None:
        json_ld = _parse_json_ld(soup)

    image_url = None

    # Strategy 1: JSON-LD
    if json_ld and 'image' in json_ld:
        image_data = json_ld['image']
        if isinstance(image_data, dict) and 'url' in image_data:
            image_url = image_data['url']
        elif isinstance(image_data, str):
            image_url = image_data

    # Strategy 2: Open Graph
    if not image_url:
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content']

    # Strategy 3: Twitter
    if not image_url:
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            image_url = twitter_image['content']

    # Strategy 4: Article image elements
    if not image_url:
        img_selectors = [
            soup.find('figure', class_=re.compile('lead|hero|featured', re.I)),
            soup.find('div', class_=re.compile('article.*image|featured.*image', re.I)),
            soup.find('article')
        ]
        for container in img_selectors:
            if container:
                img_tag = container.find('img')
                if img_tag:
                    image_url = img_tag.get('src') or img_tag.get('data-src')
                    if image_url:
                        break

    # Validate URL
    if image_url and not image_url.startswith(('http', '/')):
        return None

    return image_url


def extract_full_article(html: str, url: str) -> Dict[str, Optional[str]]:
    """
    Extract complete article data from HTML.
    Parses HTML once and shares soup + JSON-LD across all extractors.

    Args:
        html: Article HTML content
        url: Source URL of the article

    Returns:
        Dictionary with all article fields
    """
    # Parse once, share everywhere
    soup = BeautifulSoup(html, 'lxml')
    json_ld = _parse_json_ld(soup)

    metadata = parse_article_metadata(soup=soup, json_ld=json_ld)
    content = parse_article_content(soup=soup)
    image_url = parse_article_image(soup=soup, json_ld=json_ld)

    return {
        'url': url,
        'title': metadata.get('title'),
        'date': metadata.get('date'),
        'author': metadata.get('author'),
        'content': content if content else None,
        'image_url': image_url,
        'scraped_at': datetime.now(timezone.utc).isoformat()
    }


if __name__ == '__main__':
    import sys
    from pathlib import Path

    article_path = Path('data/article_sample.html')
    if not article_path.exists():
        print(f"Sample article not found: {article_path}")
        print("Run: python -m src.scraper")
        sys.exit(1)

    html = article_path.read_text(encoding='utf-8')
    print(f"Loaded {len(html)} characters")

    test_url = 'https://www.pocketgamer.com/news/test'
    article = extract_full_article(html, test_url)
    print(json.dumps(article, indent=2, ensure_ascii=False))
