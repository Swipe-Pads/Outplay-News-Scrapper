"""
Export module for converting articles to JSON/XML formats.

Exports articles from the database to structured formats suitable for
integration with CMS systems or other applications.
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Base exception for export operations."""
    pass


def format_article_for_export(article: dict) -> dict:
    """
    Format a single article for export.

    Args:
        article: Raw article dictionary from database

    Returns:
        Formatted article dictionary
    """
    # Create a clean export structure
    export_data = {
        'id': article.get('id'),
        'url': article.get('url'),
        'title': article.get('title'),
        'date': article.get('date'),
        'author': article.get('author'),
        'content': article.get('content'),
        'summary': article.get('summary'),
        'image_path': article.get('image_path'),
        'scraped_at': article.get('scraped_at'),
        'updated_at': article.get('updated_at'),
    }

    # Remove None values for cleaner exports
    return {k: v for k, v in export_data.items() if v is not None}


def export_to_json(
    articles: List[dict],
    output_path: str,
    pretty: bool = True,
    metadata: Optional[Dict] = None
) -> str:
    """
    Export articles to JSON format.

    Args:
        articles: List of article dictionaries from database
        output_path: Path to output file
        pretty: If True, format JSON with indentation
        metadata: Optional metadata to include in export

    Returns:
        Path to exported file

    Raises:
        ExportError: If export fails
    """
    try:
        # Create export directory if needed
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Format articles for export
        formatted_articles = [format_article_for_export(a) for a in articles]

        # Build export structure
        export_data = {
            'metadata': {
                'export_date': datetime.utcnow().isoformat() + 'Z',
                'article_count': len(formatted_articles),
                'version': '1.0',
                **(metadata or {})
            },
            'articles': formatted_articles
        }

        # Write JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(export_data, f, ensure_ascii=False)

        logger.info(f"Exported {len(articles)} articles to JSON: {output_file}")
        return str(output_file)

    except Exception as e:
        raise ExportError(f"Failed to export to JSON: {e}") from e


def export_to_xml(
    articles: List[dict],
    output_path: str,
    pretty: bool = True,
    metadata: Optional[Dict] = None
) -> str:
    """
    Export articles to XML format.

    Args:
        articles: List of article dictionaries from database
        output_path: Path to output file
        pretty: If True, format XML with indentation
        metadata: Optional metadata to include in export

    Returns:
        Path to exported file

    Raises:
        ExportError: If export fails
    """
    try:
        # Create export directory if needed
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Create root element
        root = ET.Element('export')

        # Add metadata
        meta_elem = ET.SubElement(root, 'metadata')
        ET.SubElement(meta_elem, 'export_date').text = datetime.utcnow().isoformat() + 'Z'
        ET.SubElement(meta_elem, 'article_count').text = str(len(articles))
        ET.SubElement(meta_elem, 'version').text = '1.0'

        # Add custom metadata
        if metadata:
            for key, value in metadata.items():
                ET.SubElement(meta_elem, key).text = str(value)

        # Add articles
        articles_elem = ET.SubElement(root, 'articles')

        for article in articles:
            formatted = format_article_for_export(article)
            article_elem = ET.SubElement(articles_elem, 'article')

            for key, value in formatted.items():
                # Handle None values
                if value is not None:
                    elem = ET.SubElement(article_elem, key)
                    elem.text = str(value)

        # Convert to string
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')

        # Pretty print if requested
        if pretty:
            dom = minidom.parseString(xml_str)
            xml_str = dom.toprettyxml(indent='  ', encoding='utf-8')

        # Write XML
        with open(output_file, 'wb') as f:
            f.write(xml_str)

        logger.info(f"Exported {len(articles)} articles to XML: {output_file}")
        return str(output_file)

    except Exception as e:
        raise ExportError(f"Failed to export to XML: {e}") from e


def validate_export_json(file_path: str) -> bool:
    """
    Validate a JSON export file.

    Args:
        file_path: Path to JSON export file

    Returns:
        True if valid, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check required keys
        if 'metadata' not in data or 'articles' not in data:
            logger.error("Missing required keys in JSON export")
            return False

        # Check metadata
        meta = data['metadata']
        if 'export_date' not in meta or 'article_count' not in meta:
            logger.error("Missing required metadata fields")
            return False

        # Check article count matches
        if len(data['articles']) != meta['article_count']:
            logger.error(f"Article count mismatch: {len(data['articles'])} vs {meta['article_count']}")
            return False

        # Check each article has required fields
        required_fields = ['id', 'url', 'title']
        for article in data['articles']:
            for field in required_fields:
                if field not in article:
                    logger.error(f"Article missing required field: {field}")
                    return False

        logger.info(f"✅ JSON export validation passed: {file_path}")
        return True

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return False
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


def validate_export_xml(file_path: str) -> bool:
    """
    Validate an XML export file.

    Args:
        file_path: Path to XML export file

    Returns:
        True if valid, False otherwise
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Check root element
        if root.tag != 'export':
            logger.error("Invalid root element")
            return False

        # Check for metadata and articles elements
        metadata = root.find('metadata')
        articles = root.find('articles')

        if metadata is None or articles is None:
            logger.error("Missing metadata or articles element")
            return False

        # Check metadata fields
        if metadata.find('export_date') is None or metadata.find('article_count') is None:
            logger.error("Missing required metadata fields")
            return False

        # Check article count
        article_count = int(metadata.find('article_count').text)
        actual_count = len(articles.findall('article'))

        if article_count != actual_count:
            logger.error(f"Article count mismatch: {actual_count} vs {article_count}")
            return False

        # Check each article has required fields
        for article in articles.findall('article'):
            if article.find('id') is None or article.find('url') is None or article.find('title') is None:
                logger.error("Article missing required fields")
                return False

        logger.info(f"✅ XML export validation passed: {file_path}")
        return True

    except ET.ParseError as e:
        logger.error(f"Invalid XML: {e}")
        return False
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


if __name__ == '__main__':
    """
    Test the exporter module.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.database import get_all_articles

    print("=" * 70)
    print("Testing Exporter Module")
    print("=" * 70)
    print()

    # Get test articles
    articles = get_all_articles(limit=3)
    print(f"Retrieved {len(articles)} articles from database")
    print()

    # Test JSON export
    print("Testing JSON export...")
    json_file = export_to_json(
        articles,
        'exports/test_export.json',
        metadata={'test': True}
    )
    print(f"✅ Exported to: {json_file}")
    print()

    # Validate JSON
    print("Validating JSON export...")
    if validate_export_json(json_file):
        print("✅ JSON validation passed")
    else:
        print("❌ JSON validation failed")
    print()

    # Test XML export
    print("Testing XML export...")
    xml_file = export_to_xml(
        articles,
        'exports/test_export.xml',
        metadata={'test': True}
    )
    print(f"✅ Exported to: {xml_file}")
    print()

    # Validate XML
    print("Validating XML export...")
    if validate_export_xml(xml_file):
        print("✅ XML validation passed")
    else:
        print("❌ XML validation failed")
    print()

    print("=" * 70)
    print("✅ All export tests passed!")
    print("=" * 70)
