"""
End-to-end article processing pipeline.

Orchestrates: scraping → parsing → image download → database storage
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper import fetch_page
from src.parser import extract_full_article
from src.image_downloader import download_image, ImageDownloadError
from src.database import init_db, insert_article, article_exists, DatabaseError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_single_article(url: str, skip_existing: bool = True) -> Optional[Dict]:
    """
    Process a single article through the complete pipeline.

    Steps:
    1. Check if article already exists (optional skip)
    2. Fetch article HTML
    3. Extract all metadata, content, and image URL
    4. Download and validate article image
    5. Store article in database with image path

    Args:
        url: Article URL to process
        skip_existing: If True, skip articles that already exist in DB

    Returns:
        Article dictionary with all fields, or None if failed/skipped

    Raises:
        Exception: Re-raises any unhandled exceptions for caller to handle
    """
    logger.info(f"Processing article: {url}")

    # Step 0: Initialize database if needed
    try:
        init_db()
    except DatabaseError as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Step 1: Check if article already exists
    if skip_existing:
        try:
            if article_exists(url):
                logger.info(f"Article already exists, skipping: {url}")
                return None
        except DatabaseError as e:
            logger.warning(f"Could not check if article exists: {e}")
            # Continue anyway

    # Step 2: Fetch article HTML
    try:
        logger.info("Fetching article HTML...")
        html = fetch_page(url)
        logger.info(f"Fetched {len(html)} characters of HTML")
    except Exception as e:
        logger.error(f"Failed to fetch article: {e}")
        raise

    # Step 3: Extract article data
    try:
        logger.info("Extracting article data...")
        article = extract_full_article(html, url)

        # Validate required fields
        if not article.get('title'):
            raise ValueError("Article title is missing")

        logger.info(f"Extracted: {article['title']}")
        logger.info(f"  - Author: {article.get('author', 'Unknown')}")
        logger.info(f"  - Date: {article.get('date', 'Unknown')}")
        logger.info(f"  - Content: {len(article.get('content', ''))} chars")
        logger.info(f"  - Image URL: {article.get('image_url', 'None')}")
    except Exception as e:
        logger.error(f"Failed to extract article data: {e}")
        raise

    # Step 4: Download article image
    image_path = None
    if article.get('image_url'):
        try:
            logger.info(f"Downloading image: {article['image_url']}")
            image_path = download_image(article['image_url'])
            logger.info(f"Image saved to: {image_path}")
            article['image_path'] = image_path
        except ImageDownloadError as e:
            logger.warning(f"Image download failed: {e}")
            # Continue without image - not critical
            article['image_path'] = None
        except Exception as e:
            logger.warning(f"Unexpected error downloading image: {e}")
            article['image_path'] = None
    else:
        logger.info("No image URL found, skipping image download")
        article['image_path'] = None

    # Step 5: Store in database
    try:
        logger.info("Storing article in database...")
        article_id = insert_article(article)
        logger.info(f"Article stored with ID: {article_id}")
        article['id'] = article_id
    except DatabaseError as e:
        logger.error(f"Failed to store article: {e}")
        # Clean up downloaded image if DB insert failed
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
                logger.info("Cleaned up image after DB failure")
            except Exception:
                pass
        raise

    logger.info(f"✅ Successfully processed article: {article['title']}")
    return article


def main():
    """CLI entry point for processing articles."""
    parser = argparse.ArgumentParser(
        description='Process a single article through the complete pipeline'
    )
    parser.add_argument(
        '--url',
        required=True,
        help='Article URL to process'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Process even if article already exists'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        result = process_single_article(
            args.url,
            skip_existing=not args.force
        )

        if result:
            print("\n" + "=" * 60)
            print("✅ PIPELINE SUCCESS")
            print("=" * 60)
            print(f"Article ID: {result.get('id')}")
            print(f"Title: {result['title']}")
            print(f"URL: {result['url']}")
            print(f"Image: {result.get('image_path', 'No image')}")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n⚠️  Article skipped (already exists)")
            sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        print("\n" + "=" * 60)
        print("❌ PIPELINE FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()
