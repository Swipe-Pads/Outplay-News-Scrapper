"""
Cleanup and maintenance module.

Handles deletion of old articles, associated images,
and orphaned image files. Supports dry-run mode.
"""

import logging
import argparse
import sys
from pathlib import Path
from typing import Dict, List

from src.config import Config
from src.database import (
    init_db, get_all_articles, get_recent_articles,
    delete_old_articles, get_old_articles, get_article_count, DatabaseError
)

logger = logging.getLogger(__name__)


def find_old_articles(days: int = 30, db_path: str = None) -> List[dict]:
    """
    Find articles older than N days.

    Args:
        days: Age threshold in days
        db_path: Database path

    Returns:
        List of old article dicts (with image_path for cleanup)
    """
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    return get_old_articles(days=days, db_path=db_path)


def delete_article_images(articles: List[dict]) -> int:
    """
    Delete image files associated with articles.

    Args:
        articles: List of article dicts with 'image_path' field

    Returns:
        Number of images deleted
    """
    deleted = 0
    for article in articles:
        img_path = article.get('image_path')
        if not img_path:
            continue

        path = Path(img_path)
        if path.exists():
            try:
                path.unlink()
                deleted += 1
                logger.debug(f"Deleted image: {path}")

                # Remove parent dir if empty
                parent = path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    logger.debug(f"Removed empty directory: {parent}")

            except OSError as e:
                logger.warning(f"Failed to delete image {path}: {e}")

    return deleted


def find_orphaned_images(db_path: str = None) -> List[Path]:
    """
    Find image files on disk that are not referenced in the database.

    Args:
        db_path: Database path

    Returns:
        List of orphaned image file paths
    """
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    # Get all image paths from DB
    articles = get_all_articles(db_path=db_path)
    db_image_paths = set()
    for a in articles:
        if a.get('image_path'):
            db_image_paths.add(Path(a['image_path']).resolve())

    # Scan images directory (project root relative)
    images_dir = Path(__file__).parent.parent / 'images'
    if not images_dir.exists():
        return []

    orphans = []
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}

    for img_file in images_dir.rglob('*'):
        if img_file.is_file() and img_file.suffix.lower() in image_extensions:
            if img_file.resolve() not in db_image_paths:
                orphans.append(img_file)

    return orphans


def delete_orphaned_images(db_path: str = None) -> int:
    """Find and delete orphaned images. Returns count deleted."""
    orphans = find_orphaned_images(db_path)
    deleted = 0

    for path in orphans:
        try:
            path.unlink()
            deleted += 1
            logger.debug(f"Deleted orphan: {path}")

            # Remove parent dir if empty
            parent = path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                logger.debug(f"Removed empty directory: {parent}")

        except OSError as e:
            logger.warning(f"Failed to delete orphan {path}: {e}")

    return deleted


def run_cleanup(
    days: int = None,
    dry_run: bool = False,
    db_path: str = None
) -> Dict[str, int]:
    """
    Run full cleanup: delete old articles, their images, and orphans.

    Args:
        days: Age threshold (default: from Config)
        dry_run: If True, only report what would be deleted
        db_path: Database path

    Returns:
        Stats dict with deletion counts
    """
    if days is None:
        days = Config.ARTICLE_RETENTION_DAYS
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    init_db(db_path)

    stats = {
        'articles_deleted': 0,
        'images_deleted': 0,
        'orphans_deleted': 0,
    }

    # Find old articles
    old_articles = find_old_articles(days=days, db_path=db_path)
    orphans = find_orphaned_images(db_path=db_path)

    logger.info(f"Cleanup report (retention: {days} days):")
    logger.info(f"  Old articles to delete: {len(old_articles)}")
    logger.info(f"  Images to delete: {sum(1 for a in old_articles if a.get('image_path'))}")
    logger.info(f"  Orphaned images: {len(orphans)}")

    if dry_run:
        logger.info("DRY RUN — no changes made")
        if old_articles:
            for a in old_articles[:10]:
                logger.info(f"  Would delete: {a['title'][:60]} (scraped: {a.get('scraped_at', '?')})")
            if len(old_articles) > 10:
                logger.info(f"  ... and {len(old_articles) - 10} more")
        if orphans:
            for o in orphans[:10]:
                logger.info(f"  Would delete orphan: {o}")
        return stats

    # Delete images first (before DB records are gone)
    stats['images_deleted'] = delete_article_images(old_articles)

    # Delete old article records
    stats['articles_deleted'] = delete_old_articles(days=days, db_path=db_path)

    # Delete orphaned images
    stats['orphans_deleted'] = delete_orphaned_images(db_path=db_path)

    logger.info(f"Cleanup complete: {stats['articles_deleted']} articles, "
                f"{stats['images_deleted']} images, "
                f"{stats['orphans_deleted']} orphans deleted")

    return stats


def main():
    """CLI entry point for cleanup."""
    parser = argparse.ArgumentParser(description='Cleanup old articles and orphaned images')
    parser.add_argument('--days', type=int, default=Config.ARTICLE_RETENTION_DAYS,
                        help=f'Delete articles older than N days (default: {Config.ARTICLE_RETENTION_DAYS})')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview what would be deleted without actually deleting')
    parser.add_argument('--orphans-only', action='store_true',
                        help='Only clean up orphaned images')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        if args.orphans_only:
            orphans = find_orphaned_images()
            if not orphans:
                print("No orphaned images found")
            elif args.dry_run:
                print(f"Found {len(orphans)} orphaned images:")
                for o in orphans:
                    print(f"  {o}")
            else:
                deleted = delete_orphaned_images()
                print(f"Deleted {deleted} orphaned images")
        else:
            stats = run_cleanup(days=args.days, dry_run=args.dry_run)
            mode = "DRY RUN" if args.dry_run else "CLEANUP"
            print(f"\n{mode} complete:")
            print(f"  Articles deleted: {stats['articles_deleted']}")
            print(f"  Images deleted: {stats['images_deleted']}")
            print(f"  Orphans deleted: {stats['orphans_deleted']}")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
