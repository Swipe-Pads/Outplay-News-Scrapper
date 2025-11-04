"""
CLI tool for summarizing articles using AI.

Usage:
    python src/summarize_cli.py --id 1                    # Summarize article by ID
    python src/summarize_cli.py --url "https://..."       # Summarize article by URL
    python src/summarize_cli.py --all                     # Summarize all articles without summaries
    python src/summarize_cli.py --all --force             # Re-summarize all articles
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    get_article_by_url,
    get_all_articles,
    insert_article,
    DatabaseError
)
from src.summarizer import summarize_article, cost_tracker, SummarizationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def summarize_by_id(article_id: int) -> bool:
    """
    Summarize a single article by ID.

    Args:
        article_id: Database ID of the article

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get articles and find the one with matching ID
        articles = get_all_articles()
        article = next((a for a in articles if a['id'] == article_id), None)

        if not article:
            logger.error(f"Article with ID {article_id} not found")
            return False

        return summarize_single_article(article)

    except Exception as e:
        logger.error(f"Failed to summarize article {article_id}: {e}")
        return False


def summarize_by_url(url: str) -> bool:
    """
    Summarize a single article by URL.

    Args:
        url: Article URL

    Returns:
        True if successful, False otherwise
    """
    try:
        article = get_article_by_url(url)

        if not article:
            logger.error(f"Article not found: {url}")
            return False

        return summarize_single_article(article)

    except Exception as e:
        logger.error(f"Failed to summarize article: {e}")
        return False


def summarize_single_article(article: dict) -> bool:
    """
    Summarize a single article and update database.

    Args:
        article: Article dictionary from database

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Summarizing: {article['title']}")

        # Check if already has summary
        if article.get('summary'):
            logger.info("Article already has a summary:")
            logger.info(f"  {article['summary']}")
            return True

        # Generate summary
        summary = summarize_article(article['title'], article['content'])

        # Update article in database
        article['summary'] = summary
        insert_article(article)

        logger.info("✅ Summary generated:")
        logger.info(f"  {summary}")
        logger.info(f"  Length: {len(summary)} chars, Bullets: {summary.count('•')}")

        return True

    except SummarizationError as e:
        logger.error(f"Summarization failed: {e}")
        return False
    except DatabaseError as e:
        logger.error(f"Database update failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


def summarize_all_articles(force: bool = False) -> dict:
    """
    Summarize all articles that don't have summaries.

    Args:
        force: If True, re-summarize articles that already have summaries

    Returns:
        Dictionary with statistics
    """
    try:
        articles = get_all_articles()

        stats = {
            'total': len(articles),
            'processed': 0,
            'skipped': 0,
            'failed': 0
        }

        logger.info(f"Found {stats['total']} articles")
        logger.info(f"Force mode: {'ON' if force else 'OFF'}")
        logger.info("=" * 60)

        for i, article in enumerate(articles, 1):
            logger.info(f"\n[{i}/{stats['total']}] {article['title'][:50]}...")

            # Skip if already has summary (unless force mode)
            if article.get('summary') and not force:
                logger.info("  ⏭️  Skipped (already has summary)")
                stats['skipped'] += 1
                continue

            try:
                # Generate summary
                summary = summarize_article(article['title'], article['content'])

                # Update database
                article['summary'] = summary
                insert_article(article)

                logger.info(f"  ✅ {summary[:60]}...")
                logger.info(f"     ({len(summary)} chars, {summary.count('•')} bullets)")
                stats['processed'] += 1

            except Exception as e:
                logger.error(f"  ❌ Failed: {e}")
                stats['failed'] += 1

        logger.info("\n" + "=" * 60)
        logger.info("SUMMARIZATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total articles: {stats['total']}")
        logger.info(f"✅ Processed: {stats['processed']}")
        logger.info(f"⏭️  Skipped: {stats['skipped']}")
        logger.info(f"❌ Failed: {stats['failed']}")
        logger.info("=" * 60)
        logger.info(f"API Cost: {cost_tracker}")
        logger.info("=" * 60)

        return stats

    except Exception as e:
        logger.error(f"Batch summarization failed: {e}")
        raise


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Summarize articles using AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/summarize_cli.py --id 1
  python src/summarize_cli.py --url "https://www.pocketgamer.com/news/..."
  python src/summarize_cli.py --all
  python src/summarize_cli.py --all --force
        """
    )

    parser.add_argument('--id', type=int, help='Article ID to summarize')
    parser.add_argument('--url', help='Article URL to summarize')
    parser.add_argument('--all', action='store_true', help='Summarize all articles without summaries')
    parser.add_argument('--force', action='store_true', help='Re-summarize articles that already have summaries')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Validate arguments
    if not any([args.id, args.url, args.all]):
        parser.error("One of --id, --url, or --all is required")

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.all:
            # Summarize all articles
            stats = summarize_all_articles(force=args.force)
            sys.exit(0 if stats['failed'] == 0 else 1)

        elif args.id:
            # Summarize by ID
            success = summarize_by_id(args.id)
            print()
            print(f"Cost tracker: {cost_tracker}")
            sys.exit(0 if success else 1)

        elif args.url:
            # Summarize by URL
            success = summarize_by_url(args.url)
            print()
            print(f"Cost tracker: {cost_tracker}")
            sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\nSummarization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
