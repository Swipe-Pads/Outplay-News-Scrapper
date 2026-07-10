"""
End-to-end article processing pipeline.

Orchestrates: source discovery -> collection -> image download -> summarization -> database storage
Supports multiple source types: websites, YouTube, Reddit.
"""

import sys
import argparse
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from src.scraper import fetch_page, parse_article_links
from src.parser import extract_full_article
from src.image_downloader import download_image, ImageDownloadError
from src.database import (
    init_db, insert_article, article_exists, get_articles_without_summary,
    update_article_summary, get_article_count, DatabaseError
)
from src.summarizer import (
    summarize_article, summarize_batch, cost_tracker,
    SummarizationError, APIKeyError
)
from src.config import Config


# Configure logging once for the whole application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_collected_item(
    item_dict: dict,
    summarize: bool = False,
    db_path: str = None
) -> Optional[Dict]:
    """
    Process a pre-collected item through image download + summarize + store.

    Args:
        item_dict: Dict with url, title, date, author, content, image_url,
                   source_type, source_name, content_id
        summarize: Generate AI summary
        db_path: Database path

    Returns:
        Stored article dict or None
    """
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    url = item_dict.get('url')
    title = item_dict.get('title', 'Untitled')

    # Check existence
    try:
        if article_exists(url, db_path):
            logger.debug(f"Already exists: {url}")
            return None
    except DatabaseError:
        pass

    # Download image
    image_path = None
    if item_dict.get('image_url'):
        try:
            image_path = download_image(item_dict['image_url'])
        except ImageDownloadError as e:
            logger.debug(f"Image download failed: {e}")
        except Exception as e:
            logger.warning(f"Unexpected image download error: {e}")

    # Build article dict for DB
    article = {
        'url': url,
        'title': title,
        'date': item_dict.get('date'),
        'author': item_dict.get('author'),
        'content': item_dict.get('content'),
        'image_path': image_path,
        'source_type': item_dict.get('source_type', 'website'),
        'source_name': item_dict.get('source_name', 'unknown'),
        'content_id': item_dict.get('content_id'),
    }

    # Summarize
    if summarize and article.get('content'):
        try:
            summary = summarize_article(title, article['content'])
            article['summary'] = summary
        except (SummarizationError, APIKeyError) as e:
            logger.warning(f"Summarization failed: {e}")

    # Store
    try:
        article_id = insert_article(article, db_path)
        article['id'] = article_id
        logger.info(f"Stored: [{article['source_type']}:{article['source_name']}] {title[:60]}")
        return article
    except DatabaseError as e:
        logger.error(f"Failed to store: {e}")
        if image_path:
            Path(image_path).unlink(missing_ok=True)
        return None


def scrape_all_sources(
    source_type: str = None,
    source_name: str = None,
    limit: int = 10,
    summarize: bool = False,
    rate_limit: float = None,
    db_path: str = None
) -> Dict[str, any]:
    """
    Run all registered sources (or filtered subset).

    Args:
        source_type: Filter by "website", "youtube", "reddit"
        source_name: Filter by specific source name
        limit: Max items per source
        summarize: Generate AI summaries
        rate_limit: Seconds between requests
        db_path: Database path

    Returns:
        Aggregate stats
    """
    from src.sources.registry import get_sources

    if rate_limit is None:
        rate_limit = Config.RATE_LIMIT_SECONDS
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    init_db(db_path)

    sources = get_sources(source_type=source_type, source_name=source_name)
    if not sources:
        logger.warning("No sources match the filter")
        return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0}

    stats = {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'by_source': {}}

    logger.info("=" * 60)
    logger.info(f"MULTI-SOURCE SCRAPE: {len(sources)} sources, limit {limit}/source")
    logger.info("=" * 60)

    start_time = time.time()

    for source in sources:
        source_key = f"{source.source_type}:{source.source_name}"
        source_stats = {'success': 0, 'skipped': 0, 'failed': 0}

        logger.info(f"\n--- [{source_key}] ---")

        try:
            identifiers = source.discover(limit=limit)
        except Exception as e:
            logger.error(f"[{source_key}] Discovery failed: {e}")
            stats['failed'] += 1
            continue

        for identifier in identifiers:
            stats['total'] += 1

            try:
                # Check if already exists before collecting (saves API calls)
                if article_exists(identifier, db_path):
                    stats['skipped'] += 1
                    source_stats['skipped'] += 1
                    continue
            except DatabaseError:
                pass

            try:
                item = source.collect(identifier)
                if item is None:
                    stats['failed'] += 1
                    source_stats['failed'] += 1
                    continue

                result = process_collected_item(
                    item.to_dict(), summarize=summarize, db_path=db_path
                )

                if result is None:
                    stats['skipped'] += 1
                    source_stats['skipped'] += 1
                else:
                    stats['success'] += 1
                    source_stats['success'] += 1

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                stats['failed'] += 1
                source_stats['failed'] += 1
                logger.error(f"[{source_key}] Error: {e}")

            # Rate limit
            if rate_limit > 0:
                time.sleep(rate_limit)

        stats['by_source'][source_key] = source_stats

    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("MULTI-SOURCE SCRAPE COMPLETE")
    logger.info(f"Sources: {len(sources)} | Items: {stats['total']} | "
                f"New: {stats['success']} | Skipped: {stats['skipped']} | "
                f"Failed: {stats['failed']} | Time: {elapsed:.1f}s")

    if summarize:
        logger.info(f"API cost: {cost_tracker}")

    return stats


# --- Legacy functions (backward compatibility) ---

def process_single_article(
    url: str,
    skip_existing: bool = True,
    summarize: bool = False,
    db_path: str = None
) -> Optional[Dict]:
    """Process a single article URL through the complete pipeline."""
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    if skip_existing:
        try:
            if article_exists(url, db_path):
                return None
        except DatabaseError:
            pass

    try:
        html = fetch_page(url)
        article = extract_full_article(html, url)
        if not article.get('title'):
            raise ValueError("Article title is missing")
    except Exception as e:
        logger.error(f"Failed to fetch/parse: {e}")
        raise

    article['source_type'] = 'website'
    article['source_name'] = 'manual'

    # Image download
    if article.get('image_url'):
        try:
            article['image_path'] = download_image(article['image_url'])
        except ImageDownloadError as e:
            logger.debug(f"Image download failed for {url}: {e}")
            article['image_path'] = None
        except Exception as e:
            logger.warning(f"Unexpected image download error for {url}: {e}")
            article['image_path'] = None
    else:
        article['image_path'] = None

    # Summarize
    if summarize and article.get('content'):
        try:
            article['summary'] = summarize_article(article['title'], article['content'])
        except (SummarizationError, APIKeyError) as e:
            logger.warning(f"Summarization failed for {url}: {e}")
            article['summary'] = None

    # Store
    try:
        article_id = insert_article(article, db_path)
        article['id'] = article_id
    except DatabaseError as e:
        logger.error(f"DB error: {e}")
        raise

    return article


def get_article_urls_from_listing(limit: int = 20) -> List[str]:
    """Get article URLs from Pocket Gamer (legacy)."""
    html = fetch_page('https://www.pocketgamer.com/news/')
    return parse_article_links(html, limit=limit)


def process_batch(urls, rate_limit=None, skip_existing=True, summarize=False, db_path=None):
    """Process multiple URLs (legacy)."""
    if rate_limit is None:
        rate_limit = Config.RATE_LIMIT_SECONDS
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    init_db(db_path)
    stats = {'total': len(urls), 'success': 0, 'skipped': 0, 'failed': 0, 'failed_urls': []}

    for idx, url in enumerate(urls, 1):
        try:
            result = process_single_article(url, skip_existing=skip_existing,
                                            summarize=summarize, db_path=db_path)
            if result is None:
                stats['skipped'] += 1
            else:
                stats['success'] += 1
        except KeyboardInterrupt:
            break
        except Exception as e:
            stats['failed'] += 1
            stats['failed_urls'].append(url)
            logger.error(f"[{idx}/{stats['total']}] Failed: {e}")

        if idx < stats['total'] and rate_limit > 0:
            time.sleep(rate_limit)

    return stats


def summarize_unsummarized(limit=None, db_path=None):
    """Summarize articles that lack summaries."""
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)
    init_db(db_path)
    articles = get_articles_without_summary(limit=limit, db_path=db_path)
    if not articles:
        return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}
    return summarize_batch(articles, db_path=db_path)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='SwipePads News Scraper — multi-source gaming news aggregator'
    )

    # Source selection
    parser.add_argument('--all', action='store_true',
                        help='Scrape all registered sources')
    parser.add_argument('--source-type', choices=['website', 'youtube', 'reddit'],
                        help='Filter by source type')
    parser.add_argument('--source', help='Filter by specific source name')
    parser.add_argument('--list-sources', action='store_true',
                        help='List all registered sources and exit')

    # Legacy single-source mode
    parser.add_argument('--url', help='Single article URL to process')
    parser.add_argument('--batch', action='store_true',
                        help='Legacy: scrape Pocket Gamer listing')

    # Common options
    parser.add_argument('--limit', type=int, default=10,
                        help='Items per source (default: 10)')
    parser.add_argument('--force', action='store_true',
                        help='Process even if already exists')
    parser.add_argument('--summarize', action='store_true',
                        help='Generate AI summaries')
    parser.add_argument('--summarize-existing', action='store_true',
                        help='Summarize existing articles that lack summaries')

    # Scoring & weekly digest
    parser.add_argument('--score', action='store_true',
                        help='Score recent articles 0-100 (gamer value, clustering, freshness)')
    parser.add_argument('--digest', action='store_true',
                        help='Generate the weekly HTML digest from top-scored articles')
    parser.add_argument('--since', type=int, default=7, metavar='N',
                        help='Days back for --score/--digest (default: 7)')
    parser.add_argument('--publish-digest', action='store_true',
                        help='Publish the latest digest as a DRAFT Shopify blog article')
    parser.add_argument('--no-ai-score', action='store_true',
                        help='Skip the AI gamer-value component when scoring')

    # Weekly mailing (Cloudflare Email Service)
    parser.add_argument('--send-mailing', action='store_true',
                        help='Mail the latest PUBLISHED blog digest to subscribers')
    parser.add_argument('--mailing-dry-run', action='store_true',
                        help='Preview the mailing (recipients + subject), send nothing')

    parser.add_argument('--verbose', action='store_true',
                        help='Enable DEBUG logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    db_path = str(Config.DATABASE_FULL_PATH)

    # List sources
    if args.list_sources:
        from src.sources.registry import list_sources
        sources = list_sources()
        print(f"\nRegistered sources ({len(sources)}):\n")
        for s in sources:
            print(f"  [{s['type']:8s}] {s['name']}")
        print()
        sys.exit(0)

    # Validate args
    if not any([args.all, args.source_type, args.source, args.url, args.batch,
                args.summarize_existing, args.score, args.digest, args.publish_digest,
                args.send_mailing, args.mailing_dry_run]):
        parser.error("Use --all, --source-type, --source, --url, --batch, "
                     "--summarize-existing, --score, --digest, --publish-digest, "
                     "--send-mailing, or --mailing-dry-run")

    try:
        init_db(db_path)

        exit_code = 0

        # Multi-source mode (can be combined with --score/--digest/--publish-digest)
        if args.all or args.source_type or args.source:
            stats = scrape_all_sources(
                source_type=args.source_type,
                source_name=args.source,
                limit=args.limit,
                summarize=args.summarize,
                db_path=db_path
            )
            print(f"\nDone: {stats['success']} new, {stats['skipped']} skipped, "
                  f"{stats['failed']} failed")
            if args.summarize:
                print(f"API cost: {cost_tracker}")
            if stats['failed'] != 0:
                exit_code = 1
            if not (args.score or args.digest or args.publish_digest):
                sys.exit(exit_code)

        # Score recent articles
        if args.score:
            from src.scorer import score_recent_articles
            score_stats = score_recent_articles(
                days=args.since, db_path=db_path, use_ai=not args.no_ai_score
            )
            print(f"\nScored: {score_stats['scored']}/{score_stats['total']} articles "
                  f"({score_stats['failed']} failed)")

        # Generate weekly digest
        if args.digest:
            from src.digest import generate_digest
            digest_path = generate_digest(since_days=args.since, db_path=db_path)
            print(f"\nDigest saved: {digest_path}")

        # Publish latest digest as Shopify draft
        if args.publish_digest:
            from src.shopify_publisher import publish_digest_draft, ShopifyPublishError
            try:
                shopify_article = publish_digest_draft()
                print(f"\nShopify draft created: id={shopify_article.get('id')} — "
                      f"'{shopify_article.get('title')}' (review & publish in Shopify Admin)")
            except ShopifyPublishError as e:
                print(f"\nShopify publish failed: {e}")
                sys.exit(1)

        # Weekly mailing: latest PUBLISHED blog article -> subscribers
        if args.send_mailing or args.mailing_dry_run:
            from src.mailer import run_weekly_mailing, MailerError
            try:
                mail_stats = run_weekly_mailing(dry_run=args.mailing_dry_run)
                if not args.mailing_dry_run:
                    print(f"\nMailing: {mail_stats['sent']} sent, "
                          f"{mail_stats['failed']} failed, "
                          f"{mail_stats['suppressed']} suppressed")
                    if mail_stats['failed'] > 0:
                        exit_code = 1
            except MailerError as e:
                print(f"\nMailing failed: {e}")
                sys.exit(1)

        if (args.score or args.digest or args.publish_digest
                or args.send_mailing or args.mailing_dry_run):
            sys.exit(exit_code)

        # Summarize existing
        if args.summarize_existing:
            stats = summarize_unsummarized(limit=args.limit, db_path=db_path)
            print(f"\nSummarized: {stats['success']} done, {stats['failed']} failed")
            sys.exit(0)

        # Legacy batch (Pocket Gamer only)
        elif args.batch:
            urls = get_article_urls_from_listing(limit=args.limit)
            if not urls:
                print("No articles found")
                sys.exit(0)
            stats = process_batch(urls, skip_existing=not args.force,
                                  summarize=args.summarize, db_path=db_path)
            print(f"\nBatch: {stats['success']} success, {stats['skipped']} skipped, "
                  f"{stats['failed']} failed")
            sys.exit(0)

        # Single URL
        else:
            result = process_single_article(args.url, skip_existing=not args.force,
                                            summarize=args.summarize, db_path=db_path)
            if result:
                print(f"\nSuccess: {result['title']}")
            else:
                print("Skipped (already exists)")
            sys.exit(0)

    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
