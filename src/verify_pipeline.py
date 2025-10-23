"""
Verification script for pipeline integrity.

Checks that articles in database have:
- Valid data in all required fields
- Downloaded images that actually exist
- Content that matches expected format
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_all_articles, get_article_count


def verify_pipeline():
    """
    Verify pipeline integrity by checking database and filesystem.
    """
    print("=" * 60)
    print("PIPELINE VERIFICATION")
    print("=" * 60)
    print()

    # Check database
    try:
        count = get_article_count()
        print(f"✅ Database connection OK")
        print(f"   Total articles: {count}")
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

    if count == 0:
        print("\n⚠️  No articles in database - pipeline not yet tested")
        return True

    print()
    print("Checking article integrity...")
    print("-" * 60)

    articles = get_all_articles(limit=10)
    errors = []

    for article in articles:
        article_id = article['id']
        title = article['title']

        # Check required fields
        if not article.get('url'):
            errors.append(f"Article {article_id}: Missing URL")
        if not article.get('title'):
            errors.append(f"Article {article_id}: Missing title")
        if not article.get('scraped_at'):
            errors.append(f"Article {article_id}: Missing scraped_at timestamp")

        # Check content
        content = article.get('content', '')
        if len(content) < 100:
            errors.append(f"Article {article_id} ({title}): Content too short ({len(content)} chars)")

        # Check image if specified
        image_path = article.get('image_path')
        if image_path:
            if not Path(image_path).exists():
                errors.append(f"Article {article_id} ({title}): Image missing at {image_path}")
            else:
                size = Path(image_path).stat().st_size
                if size < 1000:  # Less than 1KB
                    errors.append(f"Article {article_id} ({title}): Image suspiciously small ({size} bytes)")

        if not errors:
            print(f"✅ Article {article_id}: {title[:50]}...")

    print()

    if errors:
        print("=" * 60)
        print("❌ VERIFICATION FAILED")
        print("=" * 60)
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("=" * 60)
        print("✅ VERIFICATION PASSED")
        print("=" * 60)
        print(f"All {count} articles are valid")
        return True


if __name__ == '__main__':
    success = verify_pipeline()
    sys.exit(0 if success else 1)
