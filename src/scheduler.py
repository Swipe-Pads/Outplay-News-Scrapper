"""
Automation and scheduling module.

Runs scraping, summarization, export, and cleanup jobs on a schedule
using APScheduler. Supports daemon mode with PID file management.
"""

import os
import sys
import signal
import logging
import argparse
from pathlib import Path
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.config import Config
from src.database import init_db, get_article_count
from src.pipeline import scrape_all_sources
from src.exporter import export
from src.cleanup import run_cleanup
from src.strapi import sync as strapi_sync, StrapiSyncError

logger = logging.getLogger(__name__)

PID_FILE = Path('scheduler.pid')
DEFAULT_SCRAPE_INTERVAL_HOURS = 4
DEFAULT_SCRAPE_LIMIT = 20


def write_pid():
    """Write current process PID to file."""
    PID_FILE.write_text(str(os.getpid()))
    logger.info(f"PID {os.getpid()} written to {PID_FILE}")


def remove_pid():
    """Remove PID file."""
    PID_FILE.unlink(missing_ok=True)
    logger.info("PID file removed")


def scrape_job(limit: int = DEFAULT_SCRAPE_LIMIT, summarize: bool = True):
    """Scheduled scraping job — fetch, parse, summarize new articles from all sources."""
    logger.info("=" * 60)
    logger.info(f"SCHEDULED SCRAPE JOB — {datetime.now().isoformat()}")
    logger.info("=" * 60)

    db_path = str(Config.DATABASE_FULL_PATH)

    try:
        init_db(db_path)

        stats = scrape_all_sources(
            limit=limit,
            summarize=summarize,
            db_path=db_path
        )

        logger.info(f"Scrape complete: {stats['success']} new, "
                    f"{stats['skipped']} skipped, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Scrape job failed: {e}")


def export_job(format: str = 'json'):
    """Scheduled export job — generate export file after scraping."""
    logger.info("SCHEDULED EXPORT JOB")

    try:
        meta = export(format=format, validate=True)
        logger.info(f"Export complete: {meta.get('article_count', 0)} articles")
    except Exception as e:
        logger.error(f"Export job failed: {e}")


def cleanup_job(days: int = None):
    """Scheduled cleanup job — remove old articles and orphaned images."""
    if days is None:
        days = Config.ARTICLE_RETENTION_DAYS

    logger.info(f"SCHEDULED CLEANUP JOB (>{days} days)")

    try:
        stats = run_cleanup(days=days, dry_run=False)
        logger.info(f"Cleanup complete: {stats['articles_deleted']} articles, "
                    f"{stats['images_deleted']} images, "
                    f"{stats['orphans_deleted']} orphans")
    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")


def strapi_sync_job(batch_size: int = 20, publish: bool = None):
    """Scheduled Strapi sync job — push new articles to CMS."""
    logger.info("SCHEDULED STRAPI SYNC JOB")

    try:
        if publish is None:
            publish = Config.STRAPI_PUBLISH
        stats = strapi_sync(batch_size=batch_size, publish=publish)
        logger.info(f"Strapi sync: {stats['created']} created, "
                    f"{stats['updated']} updated, {stats['failed']} failed")
    except Exception as e:
        logger.error(f"Strapi sync job failed: {e}")


def health_check():
    """Check system health and log status."""
    db_path = str(Config.DATABASE_FULL_PATH)
    try:
        init_db(db_path)
        count = get_article_count(db_path)
        db_exists = Path(db_path).exists()
        db_size = Path(db_path).stat().st_size if db_exists else 0

        logger.info(f"HEALTH CHECK — Articles: {count} | "
                    f"DB size: {db_size / 1024:.1f} KB | "
                    f"Status: OK")
        return True
    except Exception as e:
        logger.error(f"HEALTH CHECK FAILED: {e}")
        return False


def create_scheduler(
    scrape_hours: int = DEFAULT_SCRAPE_INTERVAL_HOURS,
    scrape_limit: int = DEFAULT_SCRAPE_LIMIT,
    summarize: bool = True,
    enable_export: bool = True,
    enable_cleanup: bool = True,
    enable_strapi: bool = True,
    export_format: str = 'json'
) -> BlockingScheduler:
    """
    Create and configure the scheduler with all jobs.

    Args:
        scrape_hours: Hours between scrape runs
        scrape_limit: Max articles per scrape
        summarize: Generate AI summaries
        enable_export: Auto-export after scrape
        enable_cleanup: Daily cleanup of old articles
        enable_strapi: Auto-sync to Strapi CMS
        export_format: Export format ('json' or 'xml')

    Returns:
        Configured BlockingScheduler
    """
    scheduler = BlockingScheduler()

    # Scrape job — every N hours
    scheduler.add_job(
        scrape_job,
        trigger=IntervalTrigger(hours=scrape_hours),
        kwargs={'limit': scrape_limit, 'summarize': summarize},
        id='scrape_job',
        name=f'Scrape articles (every {scrape_hours}h)',
        next_run_time=datetime.now()  # Run immediately on start
    )

    # Export job — 5 min after each scrape interval
    if enable_export:
        scheduler.add_job(
            export_job,
            trigger=IntervalTrigger(hours=scrape_hours, minutes=5),
            kwargs={'format': export_format},
            id='export_job',
            name=f'Export articles (every {scrape_hours}h)',
        )

    # Cleanup job — once daily at 3 AM
    if enable_cleanup:
        scheduler.add_job(
            cleanup_job,
            trigger=CronTrigger(hour=3, minute=0),
            id='cleanup_job',
            name='Daily cleanup',
        )

    # Strapi sync — 10 min after each scrape interval (opt-in)
    if enable_strapi and Config.STRAPI_API_TOKEN:
        scheduler.add_job(
            strapi_sync_job,
            trigger=IntervalTrigger(hours=scrape_hours, minutes=10),
            id='strapi_sync_job',
            name=f'Strapi sync (every {scrape_hours}h)',
        )

    # Health check — every hour
    scheduler.add_job(
        health_check,
        trigger=IntervalTrigger(hours=1),
        id='health_check',
        name='Hourly health check',
    )

    return scheduler


def main():
    """CLI entry point for the scheduler."""
    parser = argparse.ArgumentParser(description='SwipePads News Scraper Scheduler')
    parser.add_argument('--daemon', action='store_true',
                        help='Run in daemon mode (background)')
    parser.add_argument('--interval', type=int, default=DEFAULT_SCRAPE_INTERVAL_HOURS,
                        help=f'Hours between scrapes (default: {DEFAULT_SCRAPE_INTERVAL_HOURS})')
    parser.add_argument('--limit', type=int, default=DEFAULT_SCRAPE_LIMIT,
                        help=f'Articles per scrape (default: {DEFAULT_SCRAPE_LIMIT})')
    parser.add_argument('--no-summarize', action='store_true',
                        help='Disable AI summarization')
    parser.add_argument('--no-export', action='store_true',
                        help='Disable auto-export')
    parser.add_argument('--no-cleanup', action='store_true',
                        help='Disable auto-cleanup')
    parser.add_argument('--no-strapi', action='store_true',
                        help='Disable Strapi CMS sync')
    parser.add_argument('--health', action='store_true',
                        help='Run health check and exit')
    parser.add_argument('--stop', action='store_true',
                        help='Stop running scheduler (via PID file)')

    args = parser.parse_args()

    # Set up logging
    log_file = str(Config.LOG_FILE_FULL_PATH)
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    # Health check mode
    if args.health:
        ok = health_check()
        sys.exit(0 if ok else 1)

    # Stop mode
    if args.stop:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to PID {pid}")
                remove_pid()
            except ProcessLookupError:
                print(f"Process {pid} not found, removing stale PID file")
                remove_pid()
        else:
            print("No PID file found — scheduler may not be running")
        sys.exit(0)

    # Initialize database
    init_db(str(Config.DATABASE_FULL_PATH))

    # Create scheduler
    scheduler = create_scheduler(
        scrape_hours=args.interval,
        scrape_limit=args.limit,
        summarize=not args.no_summarize,
        enable_export=not args.no_export,
        enable_cleanup=not args.no_cleanup,
        enable_strapi=not args.no_strapi,
    )

    # Write PID
    write_pid()

    # Handle graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutdown signal received")
        scheduler.shutdown(wait=False)
        remove_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Log scheduled jobs
    logger.info("Scheduler starting with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} (next run: {job.next_run_time})")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        remove_pid()


if __name__ == '__main__':
    main()
