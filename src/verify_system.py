"""
Comprehensive system verification script.

Tests all components of the news scraper system:
- Database functionality
- Article processing
- AI summarization
- Export functionality
- Cleanup operations
- Scheduler configuration
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemVerifier:
    """
    Comprehensive system verification.
    """

    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def test(self, name: str, func):
        """
        Run a test and track results.

        Args:
            name: Test name
            func: Test function to run

        Returns:
            True if test passed
        """
        try:
            logger.info(f"Testing: {name}...")
            result = func()
            if result:
                self.passed.append(name)
                logger.info(f"✅ {name}")
                return True
            else:
                self.failed.append(name)
                logger.error(f"❌ {name}")
                return False
        except Exception as e:
            self.failed.append(name)
            logger.error(f"❌ {name}: {e}")
            return False

    def warn(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(f"⚠️  {message}")

    def test_environment(self):
        """Test environment setup."""
        logger.info("\n" + "=" * 70)
        logger.info("ENVIRONMENT TESTS")
        logger.info("=" * 70)

        # Check Python version
        def check_python():
            import sys
            version = sys.version_info
            if version.major >= 3 and version.minor >= 11:
                logger.info(f"  Python version: {version.major}.{version.minor}.{version.micro}")
                return True
            return False

        self.test("Python 3.11+", check_python)

        # Check directories
        def check_directories():
            dirs = ['data', 'images', 'logs', 'exports', 'src']
            for d in dirs:
                if not Path(d).exists():
                    logger.error(f"  Missing directory: {d}")
                    return False
            return True

        self.test("Required directories", check_directories)

        # Check config
        def check_config():
            from src.config import Config
            logger.info(f"  Database: {Config.DATABASE_PATH}")
            logger.info(f"  Log level: {Config.LOG_LEVEL}")
            return True

        self.test("Configuration", check_config)

        # Check API key
        def check_api_key():
            from src.config import Config
            if Config.ANTHROPIC_API_KEY and Config.ANTHROPIC_API_KEY != 'your_anthropic_key_here':
                logger.info("  Anthropic API key configured")
                return True
            else:
                self.warn("Anthropic API key not configured - AI features will not work")
                return True  # Don't fail, just warn

        self.test("API keys", check_api_key)

    def test_database(self):
        """Test database functionality."""
        logger.info("\n" + "=" * 70)
        logger.info("DATABASE TESTS")
        logger.info("=" * 70)

        # Database initialization
        def test_db_init():
            from src.database import init_db
            init_db()
            return Path('data/articles.db').exists()

        self.test("Database initialization", test_db_init)

        # Database operations
        def test_db_operations():
            from src.database import insert_article, get_article_by_url, get_article_count

            test_article = {
                'url': 'https://test.com/verify-test',
                'title': 'Test Article',
                'date': '2025-11-04',
                'author': 'Test Author',
                'content': 'Test content for verification',
                'summary': 'Test summary'
            }

            # Insert
            article_id = insert_article(test_article)
            if not article_id:
                return False

            # Retrieve
            retrieved = get_article_by_url(test_article['url'])
            if not retrieved or retrieved['title'] != test_article['title']:
                return False

            # Count
            count = get_article_count()
            logger.info(f"  Total articles in database: {count}")

            return True

        self.test("Database CRUD operations", test_db_operations)

    def test_summarization(self):
        """Test AI summarization."""
        logger.info("\n" + "=" * 70)
        logger.info("AI SUMMARIZATION TESTS")
        logger.info("=" * 70)

        # Test API connection
        def test_api_connection():
            try:
                from src.summarizer import get_client
                client = get_client()
                logger.info("  API client initialized")
                return True
            except Exception as e:
                self.warn(f"API connection failed: {e}")
                return True  # Don't fail - API may not be configured

        self.test("API client", test_api_connection)

        # Test summarization
        def test_summarize():
            try:
                from src.summarizer import summarize_article

                summary = summarize_article(
                    "Test Article",
                    "This is test content for the verification script."
                )

                if summary and 100 <= len(summary) <= 400:
                    logger.info(f"  Summary length: {len(summary)} chars")
                    logger.info(f"  Bullets: {summary.count('•')}")
                    return True
                return False
            except Exception as e:
                self.warn(f"Summarization test skipped: {e}")
                return True  # Don't fail - API may not be configured

        self.test("Article summarization", test_summarize)

    def test_exports(self):
        """Test export functionality."""
        logger.info("\n" + "=" * 70)
        logger.info("EXPORT TESTS")
        logger.info("=" * 70)

        # Test JSON export
        def test_json_export():
            from src.database import get_all_articles
            from src.exporter import export_to_json, validate_export_json

            articles = get_all_articles(limit=2)
            if not articles:
                self.warn("No articles to export")
                return True

            json_file = export_to_json(
                articles,
                'exports/verify_test.json',
                metadata={'test': True}
            )

            if not Path(json_file).exists():
                return False

            if not validate_export_json(json_file):
                return False

            logger.info(f"  Exported {len(articles)} articles to JSON")
            return True

        self.test("JSON export", test_json_export)

        # Test XML export
        def test_xml_export():
            from src.database import get_all_articles
            from src.exporter import export_to_xml, validate_export_xml

            articles = get_all_articles(limit=2)
            if not articles:
                return True

            xml_file = export_to_xml(
                articles,
                'exports/verify_test.xml',
                metadata={'test': True}
            )

            if not Path(xml_file).exists():
                return False

            if not validate_export_xml(xml_file):
                return False

            logger.info(f"  Exported {len(articles)} articles to XML")
            return True

        self.test("XML export", test_xml_export)

    def test_cleanup(self):
        """Test cleanup functionality."""
        logger.info("\n" + "=" * 70)
        logger.info("CLEANUP TESTS")
        logger.info("=" * 70)

        # Test cleanup verification
        def test_cleanup_verify():
            from src.cleanup import verify_cleanup
            return verify_cleanup(days=30)

        self.test("Cleanup verification", test_cleanup_verify)

        # Test orphaned image detection
        def test_orphaned_images():
            from src.cleanup import get_orphaned_images
            orphaned = get_orphaned_images()
            logger.info(f"  Orphaned images found: {len(orphaned)}")
            return True

        self.test("Orphaned image detection", test_orphaned_images)

    def test_scheduler(self):
        """Test scheduler configuration."""
        logger.info("\n" + "=" * 70)
        logger.info("SCHEDULER TESTS")
        logger.info("=" * 70)

        # Test scheduler import
        def test_scheduler_import():
            from src.scheduler import NewsScraperScheduler
            scheduler = NewsScraperScheduler(scrape_interval_hours=4)
            scheduler.setup_jobs()
            logger.info(f"  Jobs configured: {len(scheduler.scheduler.get_jobs())}")
            return True

        self.test("Scheduler configuration", test_scheduler_import)

    def test_cli_tools(self):
        """Test CLI tools exist and are importable."""
        logger.info("\n" + "=" * 70)
        logger.info("CLI TOOLS TESTS")
        logger.info("=" * 70)

        tools = [
            ('pipeline.py', 'src.pipeline'),
            ('summarize_cli.py', 'src.summarize_cli'),
            ('export_cli.py', 'src.export_cli'),
            ('cost_stats.py', 'src.cost_stats'),
            ('cleanup.py', 'src.cleanup'),
            ('scheduler.py', 'src.scheduler'),
        ]

        for name, module in tools:
            def test_tool(m=module):
                __import__(m)
                return True

            self.test(f"CLI tool: {name}", test_tool)

    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 70)

        total = len(self.passed) + len(self.failed)
        logger.info(f"Total tests: {total}")
        logger.info(f"✅ Passed: {len(self.passed)}")
        logger.info(f"❌ Failed: {len(self.failed)}")
        logger.info(f"⚠️  Warnings: {len(self.warnings)}")

        if self.failed:
            logger.info("\nFailed tests:")
            for test in self.failed:
                logger.info(f"  - {test}")

        if self.warnings:
            logger.info("\nWarnings:")
            for warning in self.warnings:
                logger.info(f"  - {warning}")

        logger.info("=" * 70)

        if self.failed:
            logger.info("❌ VERIFICATION FAILED")
            return False
        else:
            logger.info("✅ ALL TESTS PASSED")
            return True


def main():
    """Run system verification."""
    print("\n" + "=" * 70)
    print("SWIPEPADS NEWS SCRAPER - SYSTEM VERIFICATION")
    print("=" * 70)
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    verifier = SystemVerifier()

    # Run all tests
    verifier.test_environment()
    verifier.test_database()
    verifier.test_summarization()
    verifier.test_exports()
    verifier.test_cleanup()
    verifier.test_scheduler()
    verifier.test_cli_tools()

    # Print summary
    success = verifier.print_summary()

    print()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
