"""
Scheduler module for automating scraping, summarization, and exports.

Runs background jobs on a schedule:
- Scrape new articles every 4 hours
- Export articles daily
- Cleanup old articles weekly
"""

import sys
import logging
import signal
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from src.pipeline import get_article_urls_from_listing, process_batch
from src.database import get_all_articles, delete_old_articles, get_article_count
from src.exporter import export_to_json
from src.summarize_cli import summarize_all_articles
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class NewsScraperScheduler:
    """
    Scheduler for automated news scraping operations.
    """

    def __init__(self, scrape_interval_hours: int = 4):
        """
        Initialize the scheduler.

        Args:
            scrape_interval_hours: Hours between scraping runs (default: 4)
        """
        self.scheduler = BlockingScheduler()
        self.scrape_interval_hours = scrape_interval_hours
        self.is_running = False

        # Track last run times
        self.last_scrape = None
        self.last_export = None
        self.last_cleanup = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def _job_listener(self, event):
        """Listen to job execution events."""
        if event.exception:
            logger.error(f"Job {event.job_id} failed with exception: {event.exception}")
        else:
            logger.info(f"Job {event.job_id} executed successfully")

    def scrape_job(self):
        """
        Scrape new articles with summarization.
        """
        try:
            logger.info("=" * 70)
            logger.info("SCHEDULED SCRAPE JOB STARTED")
            logger.info("=" * 70)

            # Get article URLs
            urls = get_article_urls_from_listing(limit=20)

            if not urls:
                logger.warning("No article URLs found")
                return

            # Process articles with summarization
            stats = process_batch(
                urls,
                skip_existing=True,
                summarize=True
            )

            self.last_scrape = datetime.now()

            logger.info("=" * 70)
            logger.info("SCHEDULED SCRAPE JOB COMPLETED")
            logger.info(f"Processed: {stats['success']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Scrape job failed: {e}", exc_info=True)
            raise

    def export_job(self):
        """
        Export all articles to JSON.
        """
        try:
            logger.info("=" * 70)
            logger.info("SCHEDULED EXPORT JOB STARTED")
            logger.info("=" * 70)

            # Get all articles
            articles = get_all_articles()

            if not articles:
                logger.warning("No articles to export")
                return

            # Generate timestamped filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"exports/scheduled_export_{timestamp}.json"

            # Export to JSON
            export_to_json(
                articles,
                output_path,
                metadata={
                    'scheduled': True,
                    'job_type': 'daily_export'
                }
            )

            self.last_export = datetime.now()

            logger.info("=" * 70)
            logger.info("SCHEDULED EXPORT JOB COMPLETED")
            logger.info(f"Exported {len(articles)} articles to {output_path}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Export job failed: {e}", exc_info=True)
            raise

    def cleanup_job(self):
        """
        Clean up old articles (older than 30 days).
        """
        try:
            logger.info("=" * 70)
            logger.info("SCHEDULED CLEANUP JOB STARTED")
            logger.info("=" * 70)

            # Get count before cleanup
            before_count = get_article_count()

            # Delete old articles
            deleted_count = delete_old_articles(days=Config.ARTICLE_RETENTION_DAYS)

            self.last_cleanup = datetime.now()

            logger.info("=" * 70)
            logger.info("SCHEDULED CLEANUP JOB COMPLETED")
            logger.info(f"Articles before: {before_count}, Deleted: {deleted_count}, Remaining: {before_count - deleted_count}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Cleanup job failed: {e}", exc_info=True)
            raise

    def summarize_job(self):
        """
        Summarize articles that don't have summaries yet.
        """
        try:
            logger.info("=" * 70)
            logger.info("SCHEDULED SUMMARIZE JOB STARTED")
            logger.info("=" * 70)

            # Summarize all articles without summaries
            stats = summarize_all_articles(force=False)

            logger.info("=" * 70)
            logger.info("SCHEDULED SUMMARIZE JOB COMPLETED")
            logger.info(f"Processed: {stats['processed']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Summarize job failed: {e}", exc_info=True)
            raise

    def health_check(self):
        """
        Health check job - logs system status.
        """
        try:
            article_count = get_article_count()
            articles = get_all_articles(limit=1)

            status = {
                'timestamp': datetime.now().isoformat(),
                'article_count': article_count,
                'last_scrape': self.last_scrape.isoformat() if self.last_scrape else 'Never',
                'last_export': self.last_export.isoformat() if self.last_export else 'Never',
                'last_cleanup': self.last_cleanup.isoformat() if self.last_cleanup else 'Never',
                'latest_article': articles[0]['scraped_at'] if articles else 'None'
            }

            logger.info("=" * 70)
            logger.info("HEALTH CHECK")
            logger.info("=" * 70)
            for key, value in status.items():
                logger.info(f"{key}: {value}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)

    def setup_jobs(self):
        """
        Setup all scheduled jobs.
        """
        # Scrape job - every 4 hours
        self.scheduler.add_job(
            self.scrape_job,
            trigger=IntervalTrigger(hours=self.scrape_interval_hours),
            id='scrape_job',
            name='Scrape Articles',
            max_instances=1,
            coalesce=True
        )
        logger.info(f"✅ Scheduled: Scrape job (every {self.scrape_interval_hours} hours)")

        # Export job - daily at 2 AM
        self.scheduler.add_job(
            self.export_job,
            trigger=CronTrigger(hour=2, minute=0),
            id='export_job',
            name='Export Articles',
            max_instances=1,
            coalesce=True
        )
        logger.info("✅ Scheduled: Export job (daily at 2:00 AM)")

        # Cleanup job - weekly on Sunday at 3 AM
        self.scheduler.add_job(
            self.cleanup_job,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='cleanup_job',
            name='Cleanup Old Articles',
            max_instances=1,
            coalesce=True
        )
        logger.info("✅ Scheduled: Cleanup job (weekly on Sunday at 3:00 AM)")

        # Summarize job - daily at 1 AM (before export)
        self.scheduler.add_job(
            self.summarize_job,
            trigger=CronTrigger(hour=1, minute=0),
            id='summarize_job',
            name='Summarize Articles',
            max_instances=1,
            coalesce=True
        )
        logger.info("✅ Scheduled: Summarize job (daily at 1:00 AM)")

        # Health check - every hour
        self.scheduler.add_job(
            self.health_check,
            trigger=IntervalTrigger(hours=1),
            id='health_check',
            name='Health Check',
            max_instances=1,
            coalesce=True
        )
        logger.info("✅ Scheduled: Health check (every hour)")

        # Add job listener
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    def start(self, run_immediately: bool = False):
        """
        Start the scheduler.

        Args:
            run_immediately: If True, run scrape job immediately before starting schedule
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        logger.info("=" * 70)
        logger.info("STARTING NEWS SCRAPER SCHEDULER")
        logger.info("=" * 70)
        logger.info(f"Scrape interval: Every {self.scrape_interval_hours} hours")
        logger.info(f"Export schedule: Daily at 2:00 AM")
        logger.info(f"Cleanup schedule: Weekly on Sunday at 3:00 AM")
        logger.info(f"Summarize schedule: Daily at 1:00 AM")
        logger.info(f"Health check: Every hour")
        logger.info("=" * 70)

        # Setup jobs
        self.setup_jobs()

        # Run scrape job immediately if requested
        if run_immediately:
            logger.info("Running initial scrape job...")
            try:
                self.scrape_job()
            except Exception as e:
                logger.error(f"Initial scrape job failed: {e}")

        # Start scheduler
        self.is_running = True
        logger.info("✅ Scheduler started. Press Ctrl+C to stop.")
        print()

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self):
        """
        Stop the scheduler.
        """
        if not self.is_running:
            return

        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("✅ Scheduler stopped")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run the news scraper scheduler daemon'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=4,
        help='Hours between scraping runs (default: 4)'
    )
    parser.add_argument(
        '--run-now',
        action='store_true',
        help='Run scrape job immediately before starting schedule'
    )

    args = parser.parse_args()

    # Create and start scheduler
    scheduler = NewsScraperScheduler(scrape_interval_hours=args.interval)
    scheduler.start(run_immediately=args.run_now)


if __name__ == '__main__':
    main()
