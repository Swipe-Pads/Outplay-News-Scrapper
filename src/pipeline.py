"""
End-to-end article processing pipeline.

Orchestrates: scraping → parsing → image download → database storage
"""

import sys
import argparse
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper import fetch_page, parse_article_links
from src.parser import extract_full_article
from src.image_downloader import download_image, ImageDownloadError
from src.database import init_db, insert_article, article_exists, DatabaseError
from src.config import Config
from src.summarizer import summarize_article, SummarizationError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_single_article(url: str, skip_existing: bool = True, summarize: bool = False) -> Optional[Dict]:
    """
    Process a single article through the complete pipeline.

    Steps:
    1. Check if article already exists (optional skip)
    2. Fetch article HTML
    3. Extract all metadata, content, and image URL
    4. Download and validate article image
    5. Generate AI summary (optional)
    6. Store article in database with image path and summary

    Args:
        url: Article URL to process
        skip_existing: If True, skip articles that already exist in DB
        summarize: If True, generate AI summary for the article

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

    # Step 5: Generate AI summary (optional)
    if summarize and article.get('content'):
        try:
            logger.info("Generating AI summary...")
            summary = summarize_article(article['title'], article['content'])
            article['summary'] = summary
            logger.info(f"Summary generated ({len(summary)} chars)")
        except SummarizationError as e:
            logger.warning(f"Summarization failed: {e}")
            article['summary'] = None
        except Exception as e:
            logger.warning(f"Unexpected error during summarization: {e}")
            article['summary'] = None
    else:
        article['summary'] = None

    # Step 6: Store in database
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


def get_article_urls_from_listing(limit: int = 20) -> List[str]:
    """
    Get article URLs from the Pocket Gamer news listing page.

    Args:
        limit: Maximum number of URLs to return

    Returns:
        List of article URLs (unique)
    """
    logger.info(f"Fetching article listing (limit: {limit})...")

    news_url = 'https://www.pocketgamer.com/news/'

    try:
        html = fetch_page(news_url)
        urls = parse_article_links(html, limit=limit)
        logger.info(f"Found {len(urls)} article URLs")
        return urls
    except Exception as e:
        logger.error(f"Failed to fetch article listing: {e}")
        raise


def process_batch(
    urls: List[str],
    rate_limit: float = None,
    skip_existing: bool = True,
    summarize: bool = False
) -> Dict[str, any]:
    """
    Process multiple articles in batch.

    Args:
        urls: List of article URLs to process
        rate_limit: Seconds to wait between requests (default: from config)
        skip_existing: If True, skip articles that already exist
        summarize: If True, generate AI summaries for articles

    Returns:
        Dictionary with batch statistics:
        - total: Total URLs processed
        - success: Successfully processed
        - skipped: Skipped (already exist)
        - failed: Failed to process
        - failed_urls: List of URLs that failed
    """
    if rate_limit is None:
        rate_limit = Config.RATE_LIMIT_SECONDS

    stats = {
        'total': len(urls),
        'success': 0,
        'skipped': 0,
        'failed': 0,
        'failed_urls': []
    }

    logger.info("=" * 60)
    logger.info(f"BATCH PROCESSING: {stats['total']} articles")
    logger.info(f"Rate limit: {rate_limit} seconds between requests")
    logger.info(f"AI Summarization: {'ENABLED' if summarize else 'DISABLED'}")
    logger.info("=" * 60)

    start_time = time.time()

    for idx, url in enumerate(urls, 1):
        logger.info(f"\n[{idx}/{stats['total']}] Processing: {url}")

        try:
            result = process_single_article(url, skip_existing=skip_existing, summarize=summarize)

            if result is None:
                stats['skipped'] += 1
                logger.info(f"[{idx}/{stats['total']}] Skipped (already exists)")
            else:
                stats['success'] += 1
                logger.info(f"[{idx}/{stats['total']}] ✅ Success: {result['title'][:50]}...")

        except KeyboardInterrupt:
            logger.info("\nBatch processing interrupted by user")
            break

        except Exception as e:
            stats['failed'] += 1
            stats['failed_urls'].append(url)
            logger.error(f"[{idx}/{stats['total']}] ❌ Failed: {e}")
            # Continue processing remaining articles

        # Rate limiting (skip after last item)
        if idx < stats['total'] and rate_limit > 0:
            logger.debug(f"Rate limiting: waiting {rate_limit} seconds...")
            time.sleep(rate_limit)

    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("BATCH PROCESSING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total processed: {stats['total']}")
    logger.info(f"✅ Success: {stats['success']}")
    logger.info(f"⏭️  Skipped: {stats['skipped']}")
    logger.info(f"❌ Failed: {stats['failed']}")
    logger.info(f"Time elapsed: {elapsed:.1f} seconds")

    if stats['failed_urls']:
        logger.info("\nFailed URLs:")
        for url in stats['failed_urls']:
            logger.info(f"  - {url}")

        # Save failed URLs to file
        failed_log = Path('logs/failed_urls.txt')
        failed_log.parent.mkdir(parents=True, exist_ok=True)
        with open(failed_log, 'a') as f:
            f.write(f"\n# Batch run: {datetime.now().isoformat()}\n")
            for url in stats['failed_urls']:
                f.write(f"{url}\n")
        logger.info(f"\nFailed URLs saved to: {failed_log}")

    logger.info("=" * 60)

    return stats


def main():
    """CLI entry point for processing articles."""
    parser = argparse.ArgumentParser(
        description='Process articles through the complete pipeline'
    )
    parser.add_argument(
        '--url',
        help='Single article URL to process'
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Batch mode: scrape multiple articles from listing'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Number of articles to scrape in batch mode (default: 20)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Process even if article already exists'
    )
    parser.add_argument(
        '--summarize',
        action='store_true',
        help='Generate AI summaries for articles'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.batch and not args.url:
        parser.error("Either --url or --batch is required")

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.batch:
            # Batch mode: get URLs from listing and process all
            urls = get_article_urls_from_listing(limit=args.limit)

            if not urls:
                print("⚠️  No articles found to process")
                sys.exit(0)

            stats = process_batch(urls, skip_existing=not args.force, summarize=args.summarize)

            # Print summary
            print("\n" + "=" * 60)
            if stats['failed'] == 0:
                print("✅ BATCH COMPLETE")
            else:
                print("⚠️  BATCH COMPLETE (with errors)")
            print("=" * 60)
            print(f"Total: {stats['total']}")
            print(f"Success: {stats['success']}")
            print(f"Skipped: {stats['skipped']}")
            print(f"Failed: {stats['failed']}")
            print("=" * 60)

            sys.exit(0 if stats['failed'] == 0 else 1)

        else:
            # Single article mode
            result = process_single_article(
                args.url,
                skip_existing=not args.force,
                summarize=args.summarize
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
