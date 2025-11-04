"""
CLI tool for exporting articles to JSON/XML formats.

Usage:
    python src/export_cli.py --format json                      # Export all to JSON
    python src/export_cli.py --format xml                       # Export all to XML
    python src/export_cli.py --format json --output custom.json # Custom output path
    python src/export_cli.py --format json --days 7             # Last 7 days only
    python src/export_cli.py --format json --limit 10           # Limit to 10 articles
    python src/export_cli.py --format json --validate           # Export and validate
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_all_articles, get_recent_articles
from src.exporter import (
    export_to_json,
    export_to_xml,
    validate_export_json,
    validate_export_xml,
    ExportError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def generate_timestamped_filename(format: str, prefix: str = "articles") -> str:
    """
    Generate a timestamped filename for exports.

    Args:
        format: Export format ('json' or 'xml')
        prefix: Filename prefix (default: 'articles')

    Returns:
        Filename with timestamp
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{prefix}_{timestamp}.{format}"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Export articles to JSON or XML format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/export_cli.py --format json
  python src/export_cli.py --format xml --output exports/articles.xml
  python src/export_cli.py --format json --days 7
  python src/export_cli.py --format json --limit 10 --validate
        """
    )

    parser.add_argument(
        '--format',
        choices=['json', 'xml'],
        required=True,
        help='Export format (json or xml)'
    )
    parser.add_argument(
        '--output',
        help='Output file path (default: timestamped file in exports/)'
    )
    parser.add_argument(
        '--days',
        type=int,
        help='Only export articles from last N days'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of articles to export'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate export file after creation'
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        default=True,
        help='Pretty-print output (default: True)'
    )
    parser.add_argument(
        '--no-pretty',
        action='store_true',
        help='Disable pretty-printing for compact output'
    )

    args = parser.parse_args()

    try:
        # Determine pretty printing
        pretty = args.pretty and not args.no_pretty

        # Get articles based on filters
        if args.days:
            logger.info(f"Fetching articles from last {args.days} days...")
            articles = get_recent_articles(days=args.days)
        else:
            logger.info("Fetching all articles...")
            articles = get_all_articles()

        if not articles:
            print("⚠️  No articles found to export")
            sys.exit(0)

        # Apply limit if specified
        if args.limit:
            articles = articles[:args.limit]
            logger.info(f"Limited to {args.limit} articles")

        logger.info(f"Found {len(articles)} articles to export")

        # Generate output path if not specified
        if args.output:
            output_path = args.output
        else:
            filename = generate_timestamped_filename(args.format)
            output_path = f"exports/{filename}"

        # Prepare metadata
        metadata = {
            'format': args.format,
            'filter_days': args.days if args.days else None,
            'limit': args.limit if args.limit else None,
        }
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        # Export based on format
        print()
        print("=" * 70)
        print(f"EXPORTING {len(articles)} ARTICLES")
        print("=" * 70)
        print(f"Format: {args.format.upper()}")
        print(f"Output: {output_path}")
        if args.days:
            print(f"Filter: Last {args.days} days")
        if args.limit:
            print(f"Limit: {args.limit} articles")
        print("=" * 70)
        print()

        if args.format == 'json':
            export_path = export_to_json(
                articles,
                output_path,
                pretty=pretty,
                metadata=metadata
            )

            # Validate if requested
            if args.validate:
                logger.info("Validating JSON export...")
                if validate_export_json(export_path):
                    print("✅ Validation passed")
                else:
                    print("❌ Validation failed")
                    sys.exit(1)

        elif args.format == 'xml':
            export_path = export_to_xml(
                articles,
                output_path,
                pretty=pretty,
                metadata=metadata
            )

            # Validate if requested
            if args.validate:
                logger.info("Validating XML export...")
                if validate_export_xml(export_path):
                    print("✅ Validation passed")
                else:
                    print("❌ Validation failed")
                    sys.exit(1)

        # Show file info
        export_file = Path(export_path)
        file_size = export_file.stat().st_size

        print()
        print("=" * 70)
        print("✅ EXPORT COMPLETE")
        print("=" * 70)
        print(f"File: {export_path}")
        print(f"Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
        print(f"Articles: {len(articles)}")
        print("=" * 70)
        print()

        sys.exit(0)

    except ExportError as e:
        logger.error(f"Export failed: {e}")
        print()
        print("=" * 70)
        print("❌ EXPORT FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
