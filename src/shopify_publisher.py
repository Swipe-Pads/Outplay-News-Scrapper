"""
Shopify blog publisher — pushes the weekly digest as a DRAFT article
via the Shopify Admin REST API (2026-01).

Draft-first policy: articles are ALWAYS created with published=false;
a human reviews and publishes from the Shopify admin.

Auth: client credentials grant — a fresh access token (valid 24h) is
exchanged on every publish run via POST /admin/oauth/access_token.
A static SHOPIFY_ADMIN_TOKEN is supported as an optional fallback.

Env vars (see .env.example):
  SHOPIFY_STORE_DOMAIN  — e.g. dkajsi-0s.myshopify.com
  SHOPIFY_CLIENT_ID     — app client id (client credentials grant)
  SHOPIFY_CLIENT_SECRET — app client secret (needs write_content)
  SHOPIFY_ADMIN_TOKEN   — optional static fallback token (shpat_...)
  SHOPIFY_BLOG_ID       — optional; if empty the first blog is used
"""

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from src.config import Config
from src.digest import find_latest_digest, compose_excerpt

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2026-01"
REQUEST_TIMEOUT = 30


class ShopifyPublishError(Exception):
    """Base exception for Shopify publishing errors."""
    pass


def _is_set(value: str) -> bool:
    """True if an env value is present and not a placeholder."""
    value = (value or '').strip()
    return bool(value) and 'your_' not in value.lower()


def _get_domain() -> str:
    """Validate and return the store domain. Clear error, no crash."""
    domain = (Config.SHOPIFY_STORE_DOMAIN or '').strip()
    if not _is_set(domain):
        raise ShopifyPublishError(
            "SHOPIFY_STORE_DOMAIN not configured. "
            "Set it in .env (e.g. SHOPIFY_STORE_DOMAIN=dkajsi-0s.myshopify.com)."
        )
    return domain


def get_access_token(domain: str) -> str:
    """
    Get an Admin API access token.

    Preferred: client credentials grant — exchanges SHOPIFY_CLIENT_ID +
    SHOPIFY_CLIENT_SECRET for a fresh token (valid 24h) on every run.
    Fallback: static SHOPIFY_ADMIN_TOKEN if set.
    """
    client_id = (Config.SHOPIFY_CLIENT_ID or '').strip()
    client_secret = (Config.SHOPIFY_CLIENT_SECRET or '').strip()

    if _is_set(client_id) and _is_set(client_secret):
        try:
            response = requests.post(
                f"https://{domain}/admin/oauth/access_token",
                json={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'grant_type': 'client_credentials',
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            detail = ''
            if getattr(e, 'response', None) is not None:
                detail = f" — response: {e.response.text[:300]}"
            raise ShopifyPublishError(
                f"Shopify client credentials token exchange failed: {e}{detail}"
            ) from e

        token = response.json().get('access_token')
        if not token:
            raise ShopifyPublishError(
                "Shopify token exchange succeeded but returned no access_token."
            )
        logger.info("Obtained fresh Shopify access token (client credentials grant)")
        return token

    # Optional fallback: static admin token
    admin_token = (Config.SHOPIFY_ADMIN_TOKEN or '').strip()
    if _is_set(admin_token):
        logger.info("Using static SHOPIFY_ADMIN_TOKEN (fallback)")
        return admin_token

    raise ShopifyPublishError(
        "Shopify credentials not configured. Set SHOPIFY_CLIENT_ID and "
        "SHOPIFY_CLIENT_SECRET in .env (client credentials grant, app needs the "
        "write_content scope), or set a static SHOPIFY_ADMIN_TOKEN (shpat_...) "
        "as fallback."
    )


def _api_url(domain: str, path: str) -> str:
    return f"https://{domain}/admin/api/{SHOPIFY_API_VERSION}/{path}"


def _headers(token: str) -> dict:
    return {
        'X-Shopify-Access-Token': token,
        'Content-Type': 'application/json',
    }


def get_blog_id(domain: str = None, token: str = None) -> int:
    """
    Resolve the target blog ID.

    Uses SHOPIFY_BLOG_ID if set; otherwise fetches blogs.json and uses the
    first blog of the store.
    """
    configured = (Config.SHOPIFY_BLOG_ID or '').strip()
    if configured:
        try:
            return int(configured)
        except ValueError:
            raise ShopifyPublishError(
                f"SHOPIFY_BLOG_ID must be a numeric ID, got: {configured!r}"
            )

    if domain is None:
        domain = _get_domain()
    if token is None:
        token = get_access_token(domain)

    try:
        response = requests.get(
            _api_url(domain, 'blogs.json'),
            headers=_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise ShopifyPublishError(f"Failed to fetch blogs from Shopify: {e}") from e

    blogs = response.json().get('blogs', [])
    if not blogs:
        raise ShopifyPublishError(
            "The store has no blogs. Create one in Shopify Admin → Online Store → Blog posts."
        )

    blog = blogs[0]
    logger.info(f"Using first blog: '{blog.get('title')}' (id={blog.get('id')})")
    return int(blog['id'])


def default_digest_title(date: datetime = None) -> str:
    """Title pattern: 'This Week in Mobile Gaming — {Month D, YYYY}'."""
    if date is None:
        date = datetime.now(timezone.utc)
    return f"This Week in Mobile Gaming — {date:%B} {date.day}, {date.year}"


def _resolve_cover_image(html_path: Path, title: str) -> Optional[dict]:
    """
    Build the article image payload (base64 attachment + alt text).

    Uses the cover PNG matching the digest date if present, otherwise
    generates one (tags from top-scored stories). Never raises — returns
    None if no image can be produced (publishing continues without it).
    """
    try:
        from src.image_generator import (
            find_cover_for_digest, generate_cover_image, extract_topic_tags,
        )

        cover_path = find_cover_for_digest(html_path)
        if cover_path is None:
            tags = []
            try:
                from src.database import get_top_scored_articles
                top = get_top_scored_articles(
                    days=7, limit=3, db_path=str(Config.DATABASE_FULL_PATH)
                )
                tags = extract_topic_tags(top)
            except Exception as e:
                logger.debug(f"No topic tags for cover ({e}) — rendering without tags")
            cover_path = generate_cover_image(tags=tags)

        attachment = base64.b64encode(cover_path.read_bytes()).decode('ascii')
        return {
            'attachment': attachment,
            'filename': cover_path.name,
            'alt': title,
        }
    except Exception as e:
        logger.warning(f"Cover image unavailable ({e}) — publishing without image")
        return None


def publish_digest_draft(
    html_path: Path = None,
    title: str = None,
    author: str = "SwipePads",
    tags: str = "weekly digest, mobile gaming",
    attach_image: bool = True,
) -> dict:
    """
    Publish a digest HTML file as a DRAFT blog article on Shopify.

    Exchanges a fresh access token (client credentials grant) on every run,
    attaches the branded cover image, and sets a click-worthy summary_html
    excerpt composed by Claude.

    Args:
        html_path: Path to the digest HTML; defaults to the latest in data/digests
        title: Article title; defaults to "This Week in Mobile Gaming — {Month D, YYYY}"
        author: Article author name
        tags: Comma-separated tags
        attach_image: Attach the branded cover image (default True)

    Returns:
        The created article dict from Shopify.

    Raises:
        ShopifyPublishError with a clear message on any failure (no crash).
    """
    domain = _get_domain()
    token = get_access_token(domain)

    if html_path is None:
        html_path = find_latest_digest()
        if html_path is None:
            raise ShopifyPublishError(
                "No digest file found in data/digests. "
                "Generate one first: python -m src.pipeline --digest"
            )

    html_path = Path(html_path)
    if not html_path.exists():
        raise ShopifyPublishError(f"Digest file not found: {html_path}")

    body_html = html_path.read_text(encoding='utf-8')
    if not body_html.strip():
        raise ShopifyPublishError(f"Digest file is empty: {html_path}")

    if title is None:
        title = default_digest_title()

    blog_id = get_blog_id(domain, token)

    # Click-worthy listing excerpt (AI, static fallback inside — never raises)
    summary_html = f"<p>{compose_excerpt(body_html)}</p>"

    payload = {
        'article': {
            'title': title,
            'author': author,
            'tags': tags,
            'body_html': body_html,
            'summary_html': summary_html,
            'published': False,  # ALWAYS draft-first — a human publishes
        }
    }

    if attach_image:
        image = _resolve_cover_image(html_path, title)
        if image:
            payload['article']['image'] = image

    logger.info(f"Publishing draft '{title}' to blog {blog_id} on {domain}...")
    try:
        response = requests.post(
            _api_url(domain, f'blogs/{blog_id}/articles.json'),
            headers=_headers(token),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        detail = ''
        if getattr(e, 'response', None) is not None:
            detail = f" — response: {e.response.text[:300]}"
        raise ShopifyPublishError(f"Failed to create Shopify article: {e}{detail}") from e

    article = response.json().get('article', {})
    logger.info(
        f"Draft created: id={article.get('id')}, title='{article.get('title')}' "
        "(published: false — review it in Shopify Admin)"
    )
    return article
