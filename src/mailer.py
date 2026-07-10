"""
Weekly digest mailing via Cloudflare Email Service (public beta).

Flow (publish-gates-mailing): a human publishes the weekly digest post on the
Shopify blog Monday morning; the mailing run finds the latest PUBLISHED
article (published within the last 5 days, not yet in data/mailed.json),
wraps it in the email template, and sends ONE personalized email per
subscriber (individual sends beat 50-recipient batching for deliverability —
each recipient gets their own HMAC unsubscribe link).

Cloudflare API references (docs fetched 2026-07-10):
  Send email: POST https://api.cloudflare.com/client/v4/accounts/{account_id}/email/sending/send
    Auth "Authorization: Bearer <token>"; body fields: to, from, subject, html,
    text, headers (custom headers object); max 5 MiB per message.
    https://developers.cloudflare.com/email-service/api/send-emails/rest-api/
  Named addresses (REST): {"address": "user@example.com", "name": "Display Name"}
    (NOTE: the Workers binding uses {"email": ...} instead — do not mix them up)
    https://developers.cloudflare.com/email-service/examples/email-sending/recipients/
  Response: {"success": true, "result": {"message_id": "...", "delivered": [...],
    "queued": [...], "permanent_bounces": [...]}}; 429 = error code 10004
    https://developers.cloudflare.com/api/resources/email_sending/
  Limits: 50 recipients per email max; new accounts start with a conservative
    daily quota. https://developers.cloudflare.com/email-service/platform/limits/
  KV list keys: GET https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/keys
    (cursor-paginated via result_info.cursor)
    https://developers.cloudflare.com/api/resources/kv/subresources/namespaces/subresources/keys/

Env vars (see .env.example): CF_ACCOUNT_ID, CF_EMAIL_API_TOKEN, KV_NAMESPACE_ID,
MAIL_FROM, MAIL_FROM_NAME, MAIL_RATE_PER_SEC, UNSUBSCRIBE_BASE_URL, UNSUB_SECRET.
"""

import hmac
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import quote

import requests

from src.config import Config

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"
REQUEST_TIMEOUT = 30
MAX_SEND_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds; doubled per attempt on 429/5xx
MAILED_LOG_NAME = "mailed.json"
PUBLISHED_WINDOW_DAYS = 5


class MailerError(Exception):
    """Base exception for mailing errors."""
    pass


# === Provider abstraction ===

class EmailProvider(ABC):
    """Abstract transactional email provider."""

    @abstractmethod
    def send(self, to: str, subject: str, html: str, headers: dict = None) -> str:
        """
        Send a single email.

        Args:
            to: Recipient email address
            subject: Subject line
            html: HTML body
            headers: Optional custom headers (e.g. List-Unsubscribe)

        Returns:
            Provider message id.
        """
        pass


class CloudflareEmailProvider(EmailProvider):
    """
    Cloudflare Email Service REST API provider.

    POST /accounts/{account_id}/email/sending/send with Bearer auth.
    Docs: https://developers.cloudflare.com/email-service/api/send-emails/rest-api/
    """

    def __init__(
        self,
        account_id: str = None,
        api_token: str = None,
        mail_from: str = None,
        from_name: str = None,
    ):
        self.account_id = (account_id or Config.CF_ACCOUNT_ID or '').strip()
        self.api_token = (api_token or Config.CF_EMAIL_API_TOKEN or '').strip()
        self.mail_from = (mail_from or Config.MAIL_FROM or '').strip()
        self.from_name = (from_name or Config.MAIL_FROM_NAME or '').strip()

        if not self.account_id or 'your_' in self.account_id.lower():
            raise MailerError("CF_ACCOUNT_ID not configured in .env")
        if not self.api_token or 'your_' in self.api_token.lower():
            raise MailerError(
                "CF_EMAIL_API_TOKEN not configured in .env "
                "(API token with Email Sending permission)"
            )
        if not self.mail_from or 'your_' in self.mail_from.lower():
            raise MailerError(
                "MAIL_FROM not configured in .env "
                "(verified sender, e.g. digest@mail.outplay.game)"
            )

    def _send_url(self) -> str:
        return f"{CF_API_BASE}/accounts/{self.account_id}/email/sending/send"

    def send(self, to: str, subject: str, html: str, headers: dict = None) -> str:
        # Body shape per REST docs; named "from" uses {"address", "name"}
        # (REST format — the Workers binding uses {"email", "name"}).
        # https://developers.cloudflare.com/email-service/examples/email-sending/recipients/
        payload = {
            'from': {'address': self.mail_from, 'name': self.from_name},
            'to': to,
            'subject': subject,
            'html': html,
        }
        if headers:
            payload['headers'] = headers

        last_error = None
        for attempt in range(MAX_SEND_RETRIES):
            try:
                response = requests.post(
                    self._send_url(),
                    headers={
                        'Authorization': f'Bearer {self.api_token}',
                        'Content-Type': 'application/json',
                    },
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException as e:
                last_error = MailerError(f"Cloudflare send request failed: {e}")
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                continue

            # Retry on rate limit (429, CF error code 10004) and 5xx
            if response.status_code == 429 or response.status_code >= 500:
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Cloudflare send returned {response.status_code} — "
                    f"retrying in {wait:.0f}s ({attempt + 1}/{MAX_SEND_RETRIES})"
                )
                last_error = MailerError(
                    f"Cloudflare send failed with HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
                time.sleep(wait)
                continue

            if not response.ok:
                raise MailerError(
                    f"Cloudflare send failed with HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )

            data = response.json()
            if not data.get('success', False):
                raise MailerError(f"Cloudflare send unsuccessful: {data.get('errors')}")

            result = data.get('result') or {}
            # Response includes result.message_id
            # https://developers.cloudflare.com/api/resources/email_sending/
            return result.get('message_id') or 'unknown'

        raise last_error or MailerError("Cloudflare send failed after retries")


# === Unsubscribe URL (HMAC) ===

def unsubscribe_token(email: str, secret: str = None) -> str:
    """hex(HMAC_SHA256(lowercased email, UNSUB_SECRET)) — matches the Worker."""
    if secret is None:
        secret = Config.UNSUB_SECRET
    if not secret:
        raise MailerError("UNSUB_SECRET not configured in .env")
    return hmac.new(
        secret.encode('utf-8'),
        email.strip().lower().encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def unsubscribe_url(email: str) -> str:
    """Personalized unsubscribe URL: BASE?e=<email>&t=<hmac hex>."""
    base = (Config.UNSUBSCRIBE_BASE_URL or '').strip().rstrip('/')
    if not base:
        raise MailerError("UNSUBSCRIBE_BASE_URL not configured in .env")
    token = unsubscribe_token(email)
    return f"{base}?e={quote(email.strip().lower())}&t={token}"


# === Subscribers (Shopify Admin GraphQL) ===

SUBSCRIBERS_QUERY = """
query subscribers($cursor: String) {
  customers(first: 250, after: $cursor, query: "email_marketing_state:subscribed") {
    pageInfo { hasNextPage endCursor }
    nodes {
      email
      emailMarketingConsent { marketingState }
    }
  }
}
"""


def get_subscribers() -> List[str]:
    """
    Fetch subscriber emails from Shopify Admin GraphQL: customers whose
    emailMarketingConsent.marketingState == SUBSCRIBED.

    Reuses the client-credentials token exchange from shopify_publisher.
    """
    from src.shopify_publisher import (
        _get_domain, get_access_token, SHOPIFY_API_VERSION, ShopifyPublishError,
    )

    try:
        domain = _get_domain()
        token = get_access_token(domain)
    except ShopifyPublishError as e:
        raise MailerError(f"Shopify auth for subscriber fetch failed: {e}") from e

    url = f"https://{domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    emails: List[str] = []
    cursor = None

    while True:
        try:
            response = requests.post(
                url,
                headers={
                    'X-Shopify-Access-Token': token,
                    'Content-Type': 'application/json',
                },
                json={'query': SUBSCRIBERS_QUERY, 'variables': {'cursor': cursor}},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise MailerError(f"Shopify subscriber fetch failed: {e}") from e

        data = response.json()
        if data.get('errors'):
            raise MailerError(f"Shopify GraphQL errors: {data['errors']}")

        customers = (data.get('data') or {}).get('customers') or {}
        for node in customers.get('nodes', []):
            email = (node.get('email') or '').strip()
            consent = node.get('emailMarketingConsent') or {}
            if email and consent.get('marketingState') == 'SUBSCRIBED':
                emails.append(email)

        page_info = customers.get('pageInfo') or {}
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info.get('endCursor')

    logger.info(f"Fetched {len(emails)} subscribed customers from Shopify")
    return emails


# === Suppression list (Cloudflare KV) ===

def get_suppressed_emails() -> Set[str]:
    """
    Read unsubscribe suppression keys (lowercased emails) from Cloudflare KV.

    KV list-keys endpoint (cursor-paginated):
      GET /accounts/{account_id}/storage/kv/namespaces/{namespace_id}/keys
    https://developers.cloudflare.com/api/resources/kv/subresources/namespaces/subresources/keys/

    Graceful: on any failure logs a warning and returns an empty set —
    the mailing continues (unsubscribes are also honored on the next run).
    """
    account_id = (Config.CF_ACCOUNT_ID or '').strip()
    namespace_id = (Config.KV_NAMESPACE_ID or '').strip()
    # dedicated KV token (least privilege); falls back to the email token
    token = (Config.CF_KV_API_TOKEN or Config.CF_EMAIL_API_TOKEN or '').strip()

    if not (account_id and namespace_id and token):
        logger.warning("KV suppression list not configured — skipping suppression check")
        return set()

    url = (
        f"{CF_API_BASE}/accounts/{account_id}/storage/kv/"
        f"namespaces/{namespace_id}/keys"
    )
    suppressed: Set[str] = set()
    cursor = None

    try:
        while True:
            params = {'limit': 1000}
            if cursor:
                params['cursor'] = cursor
            response = requests.get(
                url,
                headers={'Authorization': f'Bearer {token}'},
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            for key in data.get('result') or []:
                name = (key.get('name') or '').strip().lower()
                if name:
                    suppressed.add(name)
            cursor = (data.get('result_info') or {}).get('cursor')
            if not cursor:
                break
    except Exception as e:
        logger.warning(f"KV suppression list unavailable ({e}) — continuing without it")
        return set()

    logger.info(f"Suppression list: {len(suppressed)} unsubscribed address(es)")
    return suppressed


# === Sending ===

def send_mailing(
    subject: str,
    article_html: str,
    recipients: List[str] = None,
    provider: EmailProvider = None,
    dry_run: bool = False,
    rate_per_sec: float = None,
) -> Dict[str, int]:
    """
    Send the digest to all subscribers — one personalized email per recipient.

    Args:
        subject: Email subject (the published article title)
        article_html: The digest article body HTML
        recipients: Override recipient list (default: Shopify subscribers)
        provider: Override email provider (default: CloudflareEmailProvider)
        dry_run: Print recipient count + first 2 emails + subject; send nothing
        rate_per_sec: Sends per second throttle (default Config.MAIL_RATE_PER_SEC)

    Returns:
        Stats dict: {'recipients', 'suppressed', 'sent', 'failed'}.
    """
    from src.email_template import render_email

    if rate_per_sec is None:
        rate_per_sec = Config.MAIL_RATE_PER_SEC
    min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0

    if recipients is None:
        recipients = get_subscribers()

    suppressed = get_suppressed_emails()
    filtered = [r for r in recipients if r.strip().lower() not in suppressed]

    stats = {
        'recipients': len(recipients),
        'suppressed': len(recipients) - len(filtered),
        'sent': 0,
        'failed': 0,
    }

    if dry_run:
        preview = ', '.join(filtered[:2]) if filtered else '(none)'
        print(f"[DRY RUN] Would send to {len(filtered)} recipient(s) "
              f"({stats['suppressed']} suppressed)")
        print(f"[DRY RUN] First recipients: {preview}")
        print(f"[DRY RUN] Subject: {subject}")
        return stats

    if not filtered:
        logger.warning("No recipients to mail after suppression filtering")
        return stats

    if provider is None:
        provider = CloudflareEmailProvider()

    logger.info(f"Sending '{subject}' to {len(filtered)} recipient(s) "
                f"at <= {rate_per_sec}/s...")

    for idx, email in enumerate(filtered, 1):
        try:
            unsub = unsubscribe_url(email)
            html = render_email(article_html, unsubscribe_url=unsub, title=subject)
            message_id = provider.send(
                to=email,
                subject=subject,
                html=html,
                # One-click unsubscribe headers improve deliverability (RFC 8058)
                headers={
                    'List-Unsubscribe': f'<{unsub}>',
                    'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
                },
            )
            stats['sent'] += 1
            logger.info(f"[{idx}/{len(filtered)}] Sent to {email} (id={message_id})")
        except MailerError as e:
            stats['failed'] += 1
            logger.error(f"[{idx}/{len(filtered)}] Failed for {email}: {e}")
        except Exception as e:
            stats['failed'] += 1
            logger.error(f"[{idx}/{len(filtered)}] Unexpected error for {email}: {e}")

        if min_interval > 0 and idx < len(filtered):
            time.sleep(min_interval)

    logger.info(f"Mailing complete: {stats['sent']} sent, {stats['failed']} failed, "
                f"{stats['suppressed']} suppressed")
    return stats


# === Weekly mailing orchestration (publish-gates-mailing) ===

def get_mailed_log_path() -> Path:
    """data/mailed.json — ids of blog articles already mailed."""
    return Config.DATABASE_FULL_PATH.parent / MAILED_LOG_NAME


def load_mailed_ids(path: Path = None) -> List[int]:
    path = path or get_mailed_log_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return [int(i) for i in data.get('mailed_article_ids', [])]
    except (ValueError, OSError) as e:
        logger.warning(f"Could not read mailed log ({e}) — treating as empty")
    return []


def record_mailed_id(article_id: int, path: Path = None) -> None:
    path = path or get_mailed_log_path()
    ids = load_mailed_ids(path)
    if article_id not in ids:
        ids.append(int(article_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({'mailed_article_ids': ids}, indent=2), encoding='utf-8'
    )


def get_latest_published_article() -> Optional[dict]:
    """
    Fetch the most recently published article from the Shopify blog
    (SHOPIFY_BLOG_ID) via Admin REST: blogs/{id}/articles.json.
    """
    from src.shopify_publisher import (
        _get_domain, get_access_token, get_blog_id,
        SHOPIFY_API_VERSION, ShopifyPublishError,
    )

    try:
        domain = _get_domain()
        token = get_access_token(domain)
        blog_id = get_blog_id(domain, token)
    except ShopifyPublishError as e:
        raise MailerError(f"Shopify auth for article fetch failed: {e}") from e

    url = (
        f"https://{domain}/admin/api/{SHOPIFY_API_VERSION}/"
        f"blogs/{blog_id}/articles.json"
    )
    try:
        response = requests.get(
            url,
            headers={'X-Shopify-Access-Token': token},
            params={'published_status': 'published', 'limit': 25},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise MailerError(f"Shopify article fetch failed: {e}") from e

    articles = [
        a for a in response.json().get('articles', []) if a.get('published_at')
    ]
    if not articles:
        return None
    articles.sort(key=lambda a: a['published_at'], reverse=True)
    return articles[0]


def _parse_shopify_datetime(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError):
        return None


def run_weekly_mailing(dry_run: bool = False) -> Dict[str, int]:
    """
    Publish-gates-mailing flow:
    1. Find the latest PUBLISHED article on the blog.
    2. Gate: published_at within the last PUBLISHED_WINDOW_DAYS days AND
       article id not yet in data/mailed.json.
    3. Send the mailing (subject = article title), then record the id.

    Dry-run: prints recipients count + first 2 emails + subject, sends nothing,
    records nothing.
    """
    article = get_latest_published_article()
    if article is None:
        logger.info("No published articles on the blog — nothing to mail")
        return {'recipients': 0, 'suppressed': 0, 'sent': 0, 'failed': 0}

    article_id = article.get('id')
    title = article.get('title') or 'This Week in Mobile Gaming'
    published_at = _parse_shopify_datetime(article.get('published_at'))

    if published_at is None or (
        datetime.now(timezone.utc) - published_at > timedelta(days=PUBLISHED_WINDOW_DAYS)
    ):
        logger.info(
            f"Latest published article '{title}' is older than "
            f"{PUBLISHED_WINDOW_DAYS} days — skipping mailing"
        )
        return {'recipients': 0, 'suppressed': 0, 'sent': 0, 'failed': 0}

    if article_id in load_mailed_ids():
        logger.info(f"Article {article_id} ('{title}') already mailed — skipping")
        return {'recipients': 0, 'suppressed': 0, 'sent': 0, 'failed': 0}

    body_html = article.get('body_html') or ''
    if not body_html.strip():
        raise MailerError(f"Published article {article_id} has an empty body")

    stats = send_mailing(subject=title, article_html=body_html, dry_run=dry_run)

    if not dry_run and stats['sent'] > 0:
        record_mailed_id(article_id)
        logger.info(f"Recorded article {article_id} in {get_mailed_log_path()}")

    return stats
