"""
Cleanup module for removing old articles and orphaned images.

Handles:
- Deleting articles older than retention period
- Removing associated image files
- Cleaning up orphaned images (images without articles)
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_all_articles, delete_old_articles, get_recent_articles
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class CleanupError(Exception):
    """Base exception for cleanup operations."""
    pass


def get_old_articles(days: int = 30) -> List[dict]:
    """
    Get articles older than specified days.

    Args:
        days: Age threshold in days (default: 30)

    Returns:
        List of old article dictionaries
    """
    try:
        all_articles = get_all_articles()
        cutoff = datetime.utcnow() - timedelta(days=days)

        old_articles = []
        for article in all_articles:
            # Parse scraped_at timestamp
            scraped_at_str = article.get('scraped_at', '')
            if not scraped_at_str:
                continue

            try:
                # Handle different timestamp formats
                if 'T' in scraped_at_str:
                    scraped_at = datetime.fromisoformat(scraped_at_str.replace('Z', '+00:00'))
                else:
                    scraped_at = datetime.strptime(scraped_at_str, '%Y-%m-%d %H:%M:%S')

                if scraped_at < cutoff:
                    old_articles.append(article)
            except ValueError as e:
                logger.warning(f"Could not parse timestamp {scraped_at_str}: {e}")
                continue

        logger.info(f"Found {len(old_articles)} articles older than {days} days")
        return old_articles

    except Exception as e:
        raise CleanupError(f"Failed to query old articles: {e}") from e


def delete_article_images(articles: List[dict]) -> Dict[str, int]:
    """
    Delete image files associated with articles.

    Args:
        articles: List of article dictionaries

    Returns:
        Dictionary with deletion statistics
    """
    stats = {
        'total': len(articles),
        'deleted': 0,
        'missing': 0,
        'errors': 0
    }

    for article in articles:
        image_path = article.get('image_path')
        if not image_path:
            continue

        try:
            img_file = Path(image_path)
            if img_file.exists():
                img_file.unlink()
                stats['deleted'] += 1
                logger.debug(f"Deleted image: {image_path}")
            else:
                stats['missing'] += 1
                logger.debug(f"Image already missing: {image_path}")
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Failed to delete image {image_path}: {e}")

    logger.info(f"Image deletion: {stats['deleted']} deleted, {stats['missing']} missing, {stats['errors']} errors")
    return stats


def get_orphaned_images() -> List[Path]:
    """
    Find image files that don't have associated articles in the database.

    Returns:
        List of orphaned image file paths
    """
    try:
        # Get all article image paths from database
        articles = get_all_articles()
        db_images: Set[str] = set()

        for article in articles:
            image_path = article.get('image_path')
            if image_path:
                db_images.add(str(Path(image_path).resolve()))

        # Get all image files from disk
        images_dir = Path('images')
        if not images_dir.exists():
            logger.info("Images directory does not exist")
            return []

        disk_images = []
        for img_file in images_dir.rglob('*'):
            if img_file.is_file() and img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                disk_images.append(img_file)

        # Find orphaned images
        orphaned = []
        for img_file in disk_images:
            if str(img_file.resolve()) not in db_images:
                orphaned.append(img_file)

        logger.info(f"Found {len(orphaned)} orphaned images out of {len(disk_images)} total images")
        return orphaned

    except Exception as e:
        raise CleanupError(f"Failed to find orphaned images: {e}") from e


def delete_orphaned_images(orphaned_images: List[Path] = None) -> int:
    """
    Delete orphaned image files.

    Args:
        orphaned_images: List of orphaned image paths (if None, will find them)

    Returns:
        Number of images deleted
    """
    try:
        if orphaned_images is None:
            orphaned_images = get_orphaned_images()

        deleted = 0
        for img_file in orphaned_images:
            try:
                img_file.unlink()
                deleted += 1
                logger.debug(f"Deleted orphaned image: {img_file}")
            except Exception as e:
                logger.error(f"Failed to delete orphaned image {img_file}: {e}")

        logger.info(f"Deleted {deleted} orphaned images")
        return deleted

    except Exception as e:
        raise CleanupError(f"Failed to delete orphaned images: {e}") from e


def cleanup_old_articles(days: int = 30, delete_images: bool = True) -> Dict[str, int]:
    """
    Complete cleanup: delete old articles and their images.

    Args:
        days: Age threshold in days (default: 30)
        delete_images: If True, also delete associated images (default: True)

    Returns:
        Dictionary with cleanup statistics
    """
    try:
        logger.info("=" * 70)
        logger.info(f"CLEANUP: Articles older than {days} days")
        logger.info("=" * 70)

        # Get old articles
        old_articles = get_old_articles(days=days)

        stats = {
            'articles_found': len(old_articles),
            'articles_deleted': 0,
            'images_deleted': 0,
            'images_missing': 0,
            'images_errors': 0
        }

        if not old_articles:
            logger.info("No old articles to clean up")
            return stats

        # Delete images first if requested
        if delete_images:
            logger.info(f"Deleting images for {len(old_articles)} old articles...")
            img_stats = delete_article_images(old_articles)
            stats['images_deleted'] = img_stats['deleted']
            stats['images_missing'] = img_stats['missing']
            stats['images_errors'] = img_stats['errors']

        # Delete articles from database
        logger.info("Deleting old articles from database...")
        deleted_count = delete_old_articles(days=days)
        stats['articles_deleted'] = deleted_count

        logger.info("=" * 70)
        logger.info("CLEANUP COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Articles deleted: {stats['articles_deleted']}")
        if delete_images:
            logger.info(f"Images deleted: {stats['images_deleted']}")
            logger.info(f"Images missing: {stats['images_missing']}")
            logger.info(f"Image errors: {stats['images_errors']}")
        logger.info("=" * 70)

        return stats

    except Exception as e:
        raise CleanupError(f"Cleanup failed: {e}") from e


def cleanup_orphaned_images() -> int:
    """
    Clean up orphaned images (images without articles).

    Returns:
        Number of images deleted
    """
    try:
        logger.info("=" * 70)
        logger.info("CLEANUP: Orphaned Images")
        logger.info("=" * 70)

        deleted_count = delete_orphaned_images()

        logger.info("=" * 70)
        logger.info("ORPHANED IMAGE CLEANUP COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Images deleted: {deleted_count}")
        logger.info("=" * 70)

        return deleted_count

    except Exception as e:
        raise CleanupError(f"Orphaned image cleanup failed: {e}") from e


def verify_cleanup(days: int = 30) -> bool:
    """
    Verify cleanup is working correctly.

    Args:
        days: Age threshold to check

    Returns:
        True if verification passed
    """
    try:
        logger.info("=" * 70)
        logger.info("VERIFYING CLEANUP FUNCTIONALITY")
        logger.info("=" * 70)

        # Check old articles
        old_articles = get_old_articles(days=days)
        logger.info(f"Old articles (>{days} days): {len(old_articles)}")

        # Check orphaned images
        orphaned_images = get_orphaned_images()
        logger.info(f"Orphaned images: {len(orphaned_images)}")

        # Check recent articles
        recent_articles = get_recent_articles(days=days)
        logger.info(f"Recent articles (<{days} days): {len(recent_articles)}")

        logger.info("=" * 70)
        logger.info("✅ Cleanup verification complete")
        logger.info("=" * 70)

        return True

    except Exception as e:
        logger.error(f"Cleanup verification failed: {e}")
        return False


if __name__ == '__main__':
    """
    Test cleanup functionality.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Clean up old articles and orphaned images'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Delete articles older than N days (default: 30)'
    )
    parser.add_argument(
        '--articles',
        action='store_true',
        help='Clean up old articles'
    )
    parser.add_argument(
        '--orphaned',
        action='store_true',
        help='Clean up orphaned images'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify cleanup (dry run)'
    )

    args = parser.parse_args()

    try:
        if args.verify:
            verify_cleanup(days=args.days)
        elif args.articles:
            cleanup_old_articles(days=args.days)
        elif args.orphaned:
            cleanup_orphaned_images()
        else:
            # Default: show what would be cleaned
            logger.info("Use --articles or --orphaned to perform cleanup")
            logger.info("Use --verify to check cleanup status")
            verify_cleanup(days=args.days)

    except CleanupError as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
