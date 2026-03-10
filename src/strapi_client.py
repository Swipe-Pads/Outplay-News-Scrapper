"""
Strapi Cloud CMS client for creating article drafts and managing media.
"""

import os
import time
import logging
import mimetypes
import requests
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class StrapiError(Exception):
    """Base Strapi error."""
    pass

class StrapiAuthError(StrapiError):
    """Authentication/authorization error."""
    pass


class StrapiClient:
    """Client for Strapi Cloud REST API v4."""

    def __init__(self, base_url: str = None, api_token: str = None):
        self.base_url = (base_url or os.getenv("STRAPI_URL", "")).rstrip("/")
        self.api_token = api_token or os.getenv("STRAPI_TOKEN", "")
        if not self.base_url or not self.api_token:
            raise StrapiAuthError("STRAPI_URL and STRAPI_TOKEN must be set")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
        })

    def _request(self, method, endpoint, json_data=None, files=None, params=None, max_retries=3):
        """Make authenticated request with retry on 429/5xx."""
        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries):
            try:
                kwargs = {"params": params, "timeout": 30}
                if json_data is not None:
                    kwargs["json"] = json_data
                    self.session.headers["Content-Type"] = "application/json"
                elif files is not None:
                    kwargs["files"] = files
                    # Remove Content-Type for multipart — let requests set it
                    self.session.headers.pop("Content-Type", None)

                response = self.session.request(method, url, **kwargs)

                if response.status_code == 401 or response.status_code == 403:
                    raise StrapiAuthError(f"Auth failed: {response.status_code} - {response.text[:200]}")

                if response.status_code == 429 or response.status_code >= 500:
                    wait = (attempt + 1) * 2
                    logger.warning(f"Strapi {response.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json() if response.text else {}

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    continue
                raise StrapiError(f"Request failed after {max_retries} attempts: {e}")

        raise StrapiError(f"Request failed after {max_retries} attempts")

    def test_connection(self) -> bool:
        """Test API connectivity."""
        try:
            self._request("GET", "/api/content-type-builder/content-types")
            logger.info("Strapi connection OK")
            return True
        except Exception as e:
            logger.error(f"Strapi connection failed: {e}")
            return False

    # --- ARTICLE OPERATIONS ---

    def create_draft_article(self, article_data: dict) -> dict:
        """
        Create article as DRAFT in Strapi.

        article_data keys:
            title, summary, body, contentType, sourceUrl, sourceName,
            originalAuthor, videoUrl, reviewStatus, scrapedAt,
            game_id, priority, relevanceScore
        """
        scraped_at = article_data.get("scrapedAt", datetime.utcnow().isoformat() + "Z")

        # Calculate expiresAt: 7 days from scrapedAt
        try:
            if isinstance(scraped_at, str):
                base_dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
            else:
                base_dt = scraped_at
            expires_at = (base_dt + timedelta(days=7)).isoformat()
        except Exception:
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

        payload = {
            "data": {
                "title": article_data["title"],
                "summary": article_data.get("summary", "")[:150],
                "body": article_data.get("body", ""),
                "contentType": article_data.get("contentType", "news"),
                "sourceUrl": article_data["sourceUrl"],
                "sourceName": article_data.get("sourceName", "Unknown"),
                "originalAuthor": article_data.get("originalAuthor"),
                "videoUrl": article_data.get("videoUrl"),
                "reviewStatus": article_data.get("reviewStatus", "pending"),
                "priority": article_data.get("priority", "normal"),
                "scrapedAt": scraped_at,
                "expiresAt": expires_at,
                "publishedAt": None,  # DRAFT — not published
            }
        }

        # Link game relation if provided
        game_id = article_data.get("game_id")
        if game_id:
            payload["data"]["game"] = {"connect": [{"id": int(game_id)}]}

        result = self._request("POST", "/api/articles", json_data=payload)
        article_id = result.get("data", {}).get("id")
        logger.info(f"Created Strapi draft article ID={article_id}: {article_data['title'][:60]}")
        return result.get("data", {})

    def article_exists(self, source_url: str) -> Optional[dict]:
        """Check if article with this sourceUrl exists. Returns article data or None."""
        params = {
            "filters[sourceUrl][$eq]": source_url,
            "fields[0]": "id",
            "fields[1]": "sourceUrl",
            "fields[2]": "title",
            "pagination[pageSize]": 1,
        }
        result = self._request("GET", "/api/articles", params=params)
        data = result.get("data", [])
        return data[0] if data else None

    def get_game_by_slug(self, slug: str) -> Optional[dict]:
        """Find Game entity by slug."""
        params = {
            "filters[slug][$eq]": slug,
            "pagination[pageSize]": 1,
        }
        result = self._request("GET", "/api/games", params=params)
        data = result.get("data", [])
        return data[0] if data else None

    def upload_thumbnail(self, image_path: str, article_id: int) -> Optional[dict]:
        """Upload local image to Strapi and link to article thumbnail field."""
        path = Path(image_path)
        if not path.exists():
            logger.warning(f"Image not found: {image_path}")
            return None

        mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"

        files = {
            "files": (path.name, open(path, "rb"), mime_type),
        }
        data = {
            "ref": "api::article.article",
            "refId": str(article_id),
            "field": "thumbnail",
        }

        try:
            # For multipart with both files and form fields, use files + data params
            url = f"{self.base_url}/api/upload"
            response = self.session.post(url, files=files, data=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Uploaded thumbnail for article {article_id}")
            return result[0] if isinstance(result, list) else result
        except Exception as e:
            logger.error(f"Thumbnail upload failed: {e}")
            return None

    def upload_thumbnail_from_url(self, image_url: str, article_id: int) -> Optional[dict]:
        """Download image from URL then upload to Strapi."""
        try:
            resp = requests.get(image_url, timeout=30, headers={"User-Agent": "OutplayNewsScraper/1.0"})
            resp.raise_for_status()

            # Determine filename
            from urllib.parse import urlparse, unquote
            parsed = urlparse(image_url)
            filename = unquote(Path(parsed.path).name) or "thumbnail.jpg"

            mime_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]

            files = {"files": (filename, resp.content, mime_type)}
            data = {
                "ref": "api::article.article",
                "refId": str(article_id),
                "field": "thumbnail",
            }

            url = f"{self.base_url}/api/upload"
            response = self.session.post(url, files=files, data=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Uploaded thumbnail from URL for article {article_id}")
            return result[0] if isinstance(result, list) else result
        except Exception as e:
            logger.error(f"Thumbnail URL upload failed: {e}")
            return None

    def archive_expired_articles(self) -> int:
        """Unpublish articles past their expiresAt date. Returns count archived."""
        now = datetime.utcnow().isoformat() + "Z"
        params = {
            "filters[expiresAt][$lt]": now,
            "filters[publishedAt][$notNull]": "true",
            "fields[0]": "id",
            "fields[1]": "title",
            "pagination[pageSize]": 100,
        }
        result = self._request("GET", "/api/articles", params=params)
        articles = result.get("data", [])

        archived = 0
        for article in articles:
            aid = article.get("id")
            try:
                self._request("PUT", f"/api/articles/{aid}", json_data={
                    "data": {"publishedAt": None}
                })
                archived += 1
                logger.info(f"Archived expired article ID={aid}")
            except Exception as e:
                logger.error(f"Failed to archive article {aid}: {e}")

        logger.info(f"Archived {archived}/{len(articles)} expired articles")
        return archived

    def cleanup_old_drafts(self, days: int = 30) -> int:
        """Delete draft articles older than N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        params = {
            "filters[publishedAt][$null]": "true",
            "filters[scrapedAt][$lt]": cutoff,
            "fields[0]": "id",
            "pagination[pageSize]": 100,
        }
        result = self._request("GET", "/api/articles", params=params)
        articles = result.get("data", [])

        deleted = 0
        for article in articles:
            aid = article.get("id")
            try:
                self._request("DELETE", f"/api/articles/{aid}")
                deleted += 1
            except Exception as e:
                logger.error(f"Failed to delete draft {aid}: {e}")

        logger.info(f"Cleaned up {deleted}/{len(articles)} old drafts")
        return deleted

    def get_article_stats(self) -> dict:
        """Get article counts by status."""
        stats = {"total": 0, "drafts": 0, "published": 0, "pending_review": 0}

        try:
            # Total
            r = self._request("GET", "/api/articles", params={"pagination[pageSize]": 1})
            stats["total"] = r.get("meta", {}).get("pagination", {}).get("total", 0)

            # Published
            r = self._request("GET", "/api/articles", params={
                "filters[publishedAt][$notNull]": "true", "pagination[pageSize]": 1
            })
            stats["published"] = r.get("meta", {}).get("pagination", {}).get("total", 0)

            stats["drafts"] = stats["total"] - stats["published"]

            # Pending review
            r = self._request("GET", "/api/articles", params={
                "filters[reviewStatus][$eq]": "pending", "pagination[pageSize]": 1
            })
            stats["pending_review"] = r.get("meta", {}).get("pagination", {}).get("total", 0)
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")

        return stats


def get_strapi_client() -> StrapiClient:
    """Convenience function to create a configured client."""
    return StrapiClient()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        client = get_strapi_client()

        if client.test_connection():
            print("✅ Strapi connection OK")
            stats = client.get_article_stats()
            print(f"📊 Stats: {stats}")

        if "--test" in sys.argv:
            test_article = {
                "title": "Test Article from Scraper",
                "summary": "This is a test article created by the Outplay News Scraper pipeline.",
                "body": "This article was automatically created to test the Strapi integration.",
                "contentType": "news",
                "sourceUrl": f"https://test.outplay.app/test-{int(time.time())}",
                "sourceName": "Test Source",
                "reviewStatus": "pending",
                "scrapedAt": datetime.utcnow().isoformat() + "Z",
                "priority": "low",
            }
            result = client.create_draft_article(test_article)
            print(f"✅ Created test article: ID={result.get('id')}")

    except StrapiAuthError as e:
        print(f"❌ Auth error: {e}")
        sys.exit(1)
    except StrapiError as e:
        print(f"❌ Strapi error: {e}")
        sys.exit(1)
