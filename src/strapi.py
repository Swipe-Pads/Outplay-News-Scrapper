"""
Strapi CMS sync module.

Syncs articles from local SQLite database to Strapi CMS via REST API.
Handles image uploads, upsert by sourceUrl, and draft/publish workflow.
"""

import hashlib
import re
import sys
import time
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, List

import requests

from src.config import Config
from src.database import (
    init_db, get_articles_not_synced, get_recent_articles,
    get_all_articles, update_article_strapi_id, DatabaseError
)

logger = logging.getLogger(__name__)


# === Exceptions ===

class StrapiSyncError(Exception):
    """Base exception for Strapi sync errors."""
    pass


class StrapiConnectionError(StrapiSyncError):
    """Strapi is unreachable."""
    pass


class StrapiAuthError(StrapiSyncError):
    """Invalid or missing API token."""
    pass


class StrapiUploadError(StrapiSyncError):
    """Image upload failed."""
    pass


# === Client ===

class StrapiClient:
    """
    Thin wrapper around requests.Session for Strapi REST API.
    Handles auth, retries, rate limiting.
    """

    def __init__(
        self,
        base_url: str = None,
        api_token: str = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit: float = 0.2,
    ):
        self.base_url = (base_url or Config.STRAPI_URL).rstrip('/')
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit = rate_limit

        token = api_token or Config.STRAPI_API_TOKEN
        if not token:
            raise StrapiAuthError("STRAPI_API_TOKEN not configured in .env")

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Execute HTTP request with retry and rate limiting."""
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if attempt > 0 or self.rate_limit > 0:
                    time.sleep(self.rate_limit)

                response = self.session.request(method, url, timeout=30, **kwargs)

                # Auth errors — don't retry
                if response.status_code in (401, 403):
                    raise StrapiAuthError(
                        f"Auth failed ({response.status_code}): {response.text[:200]}"
                    )

                # Client errors — don't retry
                if 400 <= response.status_code < 500:
                    raise StrapiSyncError(
                        f"Client error {response.status_code}: {response.text[:300]}"
                    )

                # Server errors — retry
                if response.status_code >= 500:
                    last_error = StrapiSyncError(
                        f"Server error {response.status_code}: {response.text[:200]}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    raise last_error

                return response

            except requests.exceptions.ConnectionError as e:
                last_error = StrapiConnectionError(f"Connection failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue

            except requests.exceptions.Timeout as e:
                last_error = StrapiConnectionError(f"Request timeout: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue

            except (StrapiAuthError, StrapiSyncError):
                raise

            except requests.exceptions.RequestException as e:
                last_error = StrapiSyncError(f"Request error: {e}")

        raise last_error or StrapiSyncError("Request failed after all retries")

    def health_check(self) -> bool:
        """Verify Strapi connectivity and token validity."""
        try:
            resp = self._request('GET', '/api/articles?pagination[limit]=1')
            return resp.status_code == 200
        except StrapiSyncError as e:
            logger.error(f"Strapi health check failed: {e}")
            return False

    def find_article_by_source_url(self, source_url: str) -> Optional[dict]:
        """Find an article in Strapi by sourceUrl. Returns data dict or None."""
        resp = self._request(
            'GET',
            '/api/articles',
            params={
                'filters[sourceUrl][$eq]': source_url,
                'populate': 'coverImage',
                'pagination[limit]': 1,
            }
        )
        data = resp.json().get('data', [])
        return data[0] if data else None

    def create_article(self, payload: dict) -> dict:
        """Create a new article in Strapi. Returns created article data."""
        resp = self._request(
            'POST',
            '/api/articles',
            json={'data': payload}
        )
        return resp.json().get('data', {})

    def update_article(self, document_id: str, payload: dict) -> dict:
        """Update existing article by documentId."""
        resp = self._request(
            'PUT',
            f'/api/articles/{document_id}',
            json={'data': payload}
        )
        return resp.json().get('data', {})

    def publish_article(self, document_id: str) -> dict:
        """Publish a draft article by setting publishedAt via update."""
        from datetime import datetime, timezone
        resp = self._request(
            'PUT',
            f'/api/articles/{document_id}',
            json={'data': {'publishedAt': datetime.now(timezone.utc).isoformat()}}
        )
        return resp.json().get('data', {})

    def upload_image(self, file_path: str) -> Optional[int]:
        """
        Upload an image to Strapi media library.

        Args:
            file_path: Local path to image file

        Returns:
            Media ID (int) or None if upload failed
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Image not found: {file_path}")
            return None

        try:
            with open(path, 'rb') as f:
                resp = self._request(
                    'POST',
                    '/api/upload',
                    files={'files': (path.name, f, _guess_mime_type(path))},
                )

            uploaded = resp.json()
            if isinstance(uploaded, list) and uploaded:
                media_id = uploaded[0].get('id')
                logger.debug(f"Uploaded image: {path.name} → media ID {media_id}")
                return media_id

            logger.warning(f"Unexpected upload response: {uploaded}")
            return None

        except StrapiSyncError as e:
            logger.warning(f"Image upload failed for {path.name}: {e}")
            return None


def _guess_mime_type(path: Path) -> str:
    """Guess MIME type from file extension."""
    mime_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.webp': 'image/webp', '.bmp': 'image/bmp',
    }
    return mime_map.get(path.suffix.lower(), 'application/octet-stream')


# === Mapping ===

def _slugify(text: str, suffix: str = None) -> str:
    """Generate a URL-safe slug from text, with optional suffix for uniqueness.
    Only allows [A-Za-z0-9-_.~] to match Strapi UID validation."""
    slug = text.lower().strip()
    # Replace non-ASCII and special chars with hyphens
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    if not slug:
        slug = 'untitled'
    if suffix:
        slug = f"{slug}-{suffix}"
    return slug[:200]


def map_article_to_strapi(article: dict, media_id: int = None) -> dict:
    """Convert local DB article dict to Strapi REST payload."""
    title = article.get('title', '')
    url = article.get('url', '')
    # Use URL hash suffix to guarantee unique slugs across sources
    url_hash = hashlib.md5(url.encode()).hexdigest()[:6]
    payload = {
        'title': title,
        'slug': _slugify(title, suffix=url_hash),
        'sourceUrl': url,
        'date': article.get('date'),
        'author': article.get('author'),
        'summary': article.get('summary'),
        'content': article.get('content'),
        'sourceType': article.get('source_type', 'website'),
        'sourceName': article.get('source_name'),
    }
    if media_id is not None:
        payload['coverImage'] = media_id
    return payload


# === Sync orchestrator ===

def sync(
    batch_size: int = 20,
    publish: bool = None,
    only_unsynced: bool = True,
    since_days: int = None,
    db_path: str = None,
) -> Dict[str, int]:
    """
    Sync articles from local SQLite to Strapi CMS.

    Args:
        batch_size: Max articles to sync per run
        publish: Auto-publish articles (default: from Config)
        only_unsynced: Only sync articles without strapi_id
        since_days: Sync articles from last N days
        db_path: Database path

    Returns:
        Stats dict: {total, created, updated, failed, skipped}
    """
    if publish is None:
        publish = Config.STRAPI_PUBLISH
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    stats = {'total': 0, 'created': 0, 'updated': 0, 'failed': 0, 'skipped': 0}

    # Validate config
    if not Config.STRAPI_API_TOKEN:
        logger.error("STRAPI_API_TOKEN not set — skipping sync")
        return stats

    # Initialize client
    try:
        client = StrapiClient()
    except StrapiAuthError as e:
        logger.error(f"Strapi auth error: {e}")
        return stats

    # Health check
    if not client.health_check():
        logger.error("Strapi unreachable — skipping sync")
        return stats

    # Query articles
    init_db(db_path)
    if only_unsynced:
        articles = get_articles_not_synced(limit=batch_size, db_path=db_path)
    elif since_days:
        articles = get_recent_articles(days=since_days, db_path=db_path)
        articles = articles[:batch_size]
    else:
        articles = get_all_articles(limit=batch_size, db_path=db_path)

    stats['total'] = len(articles)

    if not articles:
        logger.info("No articles to sync")
        return stats

    logger.info(f"Syncing {len(articles)} articles to Strapi ({client.base_url})")

    for idx, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')[:60]

        try:
            # Upload image if available
            media_id = None
            image_path = article.get('image_path')
            if image_path and Path(image_path).exists():
                media_id = client.upload_image(image_path)

            # Build payload
            payload = map_article_to_strapi(article, media_id=media_id)

            # Check if exists in Strapi
            existing = client.find_article_by_source_url(article['url'])

            if existing:
                document_id = existing.get('documentId')

                # Skip image re-upload if already has one
                if existing.get('coverImage') and media_id is None:
                    pass  # keep existing image

                # Update
                result = client.update_article(document_id, payload)
                stats['updated'] += 1
                logger.info(f"[{idx}/{stats['total']}] Updated: {title}")
            else:
                # Create
                result = client.create_article(payload)
                document_id = result.get('documentId')
                stats['created'] += 1
                logger.info(f"[{idx}/{stats['total']}] Created: {title}")

            # Publish if requested
            if publish and document_id:
                try:
                    client.publish_article(document_id)
                except StrapiSyncError as e:
                    logger.warning(f"Failed to publish {title}: {e}")

            # Save strapi_id to local DB
            strapi_numeric_id = result.get('id') if result else None
            if strapi_numeric_id and article.get('id'):
                update_article_strapi_id(article['id'], strapi_numeric_id, db_path)

        except StrapiSyncError as e:
            stats['failed'] += 1
            logger.error(f"[{idx}/{stats['total']}] Failed: {title} — {e}")
        except Exception as e:
            stats['failed'] += 1
            logger.error(f"[{idx}/{stats['total']}] Unexpected error for {title}: {e}")

    logger.info(f"Strapi sync complete: {stats['created']} created, "
                f"{stats['updated']} updated, {stats['failed']} failed, "
                f"{stats['skipped']} skipped")

    return stats


# === CLI ===

def main():
    """CLI entry point for Strapi sync."""
    parser = argparse.ArgumentParser(description='Sync articles to Strapi CMS')
    parser.add_argument('--sync', action='store_true', help='Run sync')
    parser.add_argument('--batch-size', type=int, default=20,
                        help='Max articles per sync (default: 20)')
    parser.add_argument('--publish', action='store_true',
                        help='Auto-publish articles')
    parser.add_argument('--all', action='store_true',
                        help='Sync all articles (not just unsynced)')
    parser.add_argument('--since', type=int,
                        help='Sync articles from last N days')
    parser.add_argument('--health', action='store_true',
                        help='Check Strapi connectivity and exit')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if args.health:
        try:
            client = StrapiClient()
            ok = client.health_check()
            if ok:
                print(f"Strapi OK — {client.base_url}")
            else:
                print(f"Strapi unreachable — {client.base_url}")
            sys.exit(0 if ok else 1)
        except StrapiAuthError as e:
            print(f"Auth error: {e}")
            sys.exit(1)

    if not args.sync:
        parser.error("Use --sync or --health")

    try:
        stats = sync(
            batch_size=args.batch_size,
            publish=args.publish,
            only_unsynced=not args.all,
            since_days=args.since,
        )
        print(f"\nSync complete: {stats['created']} created, "
              f"{stats['updated']} updated, {stats['failed']} failed")
        sys.exit(0 if stats['failed'] == 0 else 1)
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
