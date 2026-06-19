"""
Export module for generating CMS-ready JSON and XML files.

Exports articles from the database into structured formats
suitable for integration with SwipePads mobile launcher.
"""

import json
import logging
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
from defusedxml.ElementTree import parse, fromstring  # noqa: F401 — safe XML parsing
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from src.config import Config
from src.database import (
    init_db, get_all_articles, get_recent_articles,
    get_article_count, DatabaseError
)

logger = logging.getLogger(__name__)


def format_article_for_export(article: dict) -> dict:
    """Format a single article for JSON export."""
    return {
        'id': article.get('id'),
        'url': article.get('url'),
        'sourceUrl': article.get('url'),
        'title': article.get('title'),
        'date': article.get('date'),
        'author': article.get('author'),
        'summary': article.get('summary'),
        'content': article.get('content'),
        'coverImage': article.get('image_path'),
        'source': article.get('source_name', 'unknown'),
        'source_type': article.get('source_type', 'website'),
        'scraped_at': article.get('scraped_at'),
        'updated_at': article.get('updated_at'),
    }


def export_articles_json(
    output_path: str,
    articles: List[dict],
    validate: bool = False
) -> dict:
    """
    Export articles to a JSON file.

    Args:
        output_path: Path for the output JSON file
        articles: List of article dicts to export
        validate: If True, validate export integrity

    Returns:
        Export metadata dict
    """
    formatted = [format_article_for_export(a) for a in articles]

    export_data = {
        'meta': {
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'article_count': len(formatted),
            'format_version': '1.0',
            'source': 'SwipePads News Scraper',
        },
        'data': formatted
    }

    # Validate if requested
    issues = []
    if validate:
        for i, article in enumerate(formatted):
            if not article.get('title'):
                issues.append(f"Article {i}: missing title")
            if not article.get('url'):
                issues.append(f"Article {i}: missing URL")
            if article.get('coverImage'):
                img_path = Path(article['coverImage'])
                if not img_path.exists():
                    issues.append(f"Article {i}: image not found: {article['coverImage']}")

        export_data['meta']['validation'] = {
            'validated': True,
            'issues_count': len(issues),
            'issues': issues
        }

    # Write file
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(export_data, indent=2, ensure_ascii=False), encoding='utf-8')

    logger.info(f"Exported {len(formatted)} articles to {output_path}")
    if issues:
        logger.warning(f"Validation found {len(issues)} issues")
        for issue in issues:
            logger.warning(f"  - {issue}")

    return export_data['meta']


def export_articles_xml(output_path: str, articles: List[dict]) -> dict:
    """
    Export articles to an XML file.

    Args:
        output_path: Path for the output XML file
        articles: List of article dicts to export

    Returns:
        Export metadata dict
    """
    root = Element('articles')
    root.set('exported_at', datetime.now(timezone.utc).isoformat())
    root.set('count', str(len(articles)))
    root.set('source', 'SwipePads News Scraper')

    for article in articles:
        article_elem = SubElement(root, 'article')
        article_elem.set('id', str(article.get('id', '')))

        fields = ['url', 'title', 'date', 'author', 'summary', 'content',
                  'image_path', 'source_type', 'source_name', 'scraped_at', 'updated_at']
        for field in fields:
            elem = SubElement(article_elem, field)
            elem.text = str(article.get(field, '') or '')

    # Pretty print
    xml_str = parseString(tostring(root, encoding='unicode')).toprettyxml(indent='  ')

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml_str, encoding='utf-8')

    logger.info(f"Exported {len(articles)} articles to XML: {output_path}")

    return {
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'article_count': len(articles),
        'format': 'xml'
    }


def generate_export_filename(format: str = 'json') -> str:
    """Generate a timestamped export filename."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"exports/articles_{timestamp}.{format}"


def export(
    format: str = 'json',
    output: str = None,
    since_days: int = None,
    limit: int = None,
    validate: bool = False,
    db_path: str = None
) -> dict:
    """
    Main export function — query articles and write to file.

    Args:
        format: 'json' or 'xml'
        output: Output file path (auto-generated if None)
        since_days: Only export articles from last N days
        limit: Max articles to export
        validate: Validate export integrity (JSON only)
        db_path: Database path

    Returns:
        Export metadata
    """
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    init_db(db_path)

    # Query articles
    if since_days:
        articles = get_recent_articles(days=since_days, db_path=db_path)
    else:
        articles = get_all_articles(limit=limit, db_path=db_path)

    if limit and since_days:
        articles = articles[:limit]

    if not articles:
        logger.info("No articles to export")
        return {'article_count': 0}

    # Generate output path
    if output is None:
        output = generate_export_filename(format)

    # Export
    if format == 'xml':
        return export_articles_xml(output, articles)
    else:
        return export_articles_json(output, articles, validate=validate)


def main():
    """CLI entry point for exporting articles."""
    parser = argparse.ArgumentParser(description='Export articles to JSON/XML')
    parser.add_argument('--format', choices=['json', 'xml'], default='json',
                        help='Export format (default: json)')
    parser.add_argument('--output', '-o', help='Output file path (auto-generated if omitted)')
    parser.add_argument('--since', type=int, help='Export articles from last N days')
    parser.add_argument('--limit', type=int, help='Max articles to export')
    parser.add_argument('--validate', action='store_true', help='Validate export integrity')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        meta = export(
            format=args.format,
            output=args.output,
            since_days=args.since,
            limit=args.limit,
            validate=args.validate
        )

        print(f"\nExport complete: {meta.get('article_count', 0)} articles")
        if meta.get('validation'):
            v = meta['validation']
            if v['issues_count'] == 0:
                print("Validation: All checks passed")
            else:
                print(f"Validation: {v['issues_count']} issues found")

    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
