"""
Shopify blog publisher — pushes the weekly digest as a DRAFT article
via the Shopify Admin REST API (2026-01).

Draft-first policy: articles are ALWAYS created with published=false;
a human reviews and publishes from the Shopify admin.

Env vars (see .env.example):
  SHOPIFY_STORE_DOMAIN — e.g. dkajsi-0s.myshopify.com
  SHOPIFY_ADMIN_TOKEN  — Admin API access token (shpat_...), needs write_content
  SHOPIFY_BLOG_ID      — optional; if empty the first blog is used
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from src.config import Config
from src.digest import find_latest_digest

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2026-01"
REQUEST_TIMEOUT = 30


class ShopifyPublishError(Exception):
    """Base exception for Shopify publishing errors."""
    pass


def _get_credentials() -> tuple:
    """Validate and return (store_domain, admin_token). Clear errors, no crash."""
    domain = (Config.SHOPIFY_STORE_DOMAIN or '').strip()
    token = (Config.SHOPIFY_ADMIN_TOKEN or '').strip()

    if not domain or 'your_' in domain.lower():
        raise ShopifyPublishError(
            "SHOPIFY_STORE_DOMAIN not configured. "
            "Set it in .env (e.g. SHOPIFY_STORE_DOMAIN=dkajsi-0s.myshopify.com)."
        )
    if not token or 'your_' in token.lower():
        raise ShopifyPublishError(
            "SHOPIFY_ADMIN_TOKEN not configured. "
            "Create an Admin API access token (shpat_...) with the write_content "
            "scope in Shopify Admin → Settings → Apps → Develop apps, "
            "then set SHOPIFY_ADMIN_TOKEN in .env."
        )
    return domain, token


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

    if domain is None or token is None:
        domain, token = _get_credentials()

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


def publish_digest_draft(
    html_path: Path = None,
    title: str = None,
    author: str = "SwipePads",
    tags: str = "weekly digest, mobile gaming",
) -> dict:
    """
    Publish a digest HTML file as a DRAFT blog article on Shopify.

    Args:
        html_path: Path to the digest HTML; defaults to the latest in data/digests
        title: Article title; defaults to "This Week in Mobile Gaming — {Month D, YYYY}"
        author: Article author name
        tags: Comma-separated tags

    Returns:
        The created article dict from Shopify.

    Raises:
        ShopifyPublishError with a clear message on any failure (no crash).
    """
    domain, token = _get_credentials()

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

    payload = {
        'article': {
            'title': title,
            'author': author,
            'tags': tags,
            'body_html': body_html,
            'published': False,  # ALWAYS draft-first — a human publishes
        }
    }

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
