"""
Newsletter collector — reads gaming newsletters delivered to the
news.outplay.game subdomain and extracts the articles they link to.

Flow: senders mail news.outplay.game -> Cloudflare Email Routing (subdomain
catch-all) -> newsletter-inbox Worker stores raw MIME in KV (30-day TTL) ->
this collector lists recent KV entries in the weekly digest run, parses each
email and asks Claude to extract the linked articles as structured items.

There is deliberately no "processed" marker in KV: the pipeline dedupes by
article URL before collecting (article_exists), so re-reading the same email
across runs is a no-op, and the key's timestamp plus NEWSLETTER_SINCE_DAYS
bounds the scan window.

One collector is registered per configured sender so that per-source limits
and --source filtering behave like every other source. All collectors share
a single KV fetch + extraction pass per run (module-level cache), mirroring
the request-once pattern of the Reddit collector.
"""

import email
import email.policy
import json
import logging
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

import requests

from src.config import Config
from src.sources.base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"
_TIMEOUT = 20
_MAX_EMAIL_CHARS = 28000   # HTML passed to Claude per email
_MAX_ITEMS_PER_EMAIL = 20

# Senders we subscribe to with the news@ address. `match` is tested against
# the From header (substring, case-insensitive). Order matters: the first
# match wins, so blocks must precede the broader domain entries.
NEWSLETTER_SENDERS = [
    # GamesIndustry.biz sends sponsored mails from contact@ — not editorial
    {"match": "contact@gamesindustry.biz", "name": None},          # block
    {"match": "gamesindustry.biz", "name": "gamesindustry.biz"},
    {"match": "deconstructoroffun.com", "name": "deconstructoroffun"},
    {"match": "naavik", "name": "naavik"},
    {"match": "mobilegamerbiz@substack.com", "name": "mobilegamer.biz"},
    {"match": "gamingonphone.com", "name": "gamingonphone"},
    {"match": "pocketgamer.biz", "name": "pocketgamer.biz"},
    {"match": "gamerbraves", "name": "gamerbraves"},
    {"match": "gamedevreports", "name": "gamedevreports"},
    {"match": "mobiledevmemo", "name": "mobiledevmemo"},
]

# Hosts that wrap destination URLs in tracking redirects worth resolving.
_TRACKING_HOST_RE = re.compile(
    r"(^|\.)substack\.com$|^link\.|^click\.|^email\.|^url\d*\.|"
    r"(^|\.)list-manage\.com$|(^|\.)sendgrid\.net$|(^|\.)mailchi\.mp$",
    re.IGNORECASE,
)

# Link targets that are never articles.
_JUNK_URL_RE = re.compile(
    r"unsubscribe|manage.preferences|mailto:|twitter\.com|x\.com/|facebook\.com|"
    r"linkedin\.com|instagram\.com|youtube\.com/(user|channel|@)|discord\.(gg|com)|"
    r"apps\.apple\.com|play\.google\.com/store/apps/details\?id=com\.substack",
    re.IGNORECASE,
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# Per-run cache: sender name -> list of item dicts (set by _load_inbox)
_inbox: Optional[Dict[str, List[dict]]] = None


class NewsletterError(Exception):
    pass


# === Cloudflare KV access ===

def _kv_auth() -> Optional[dict]:
    """Account/namespace/token triple, or None (with a warning) if unset."""
    account_id = (Config.CF_ACCOUNT_ID or "").strip()
    namespace_id = (Config.NEWSLETTER_KV_NAMESPACE_ID or "").strip()
    token = (Config.CF_KV_API_TOKEN or Config.CF_EMAIL_API_TOKEN or "").strip()
    if not (account_id and namespace_id and token):
        logger.warning("Newsletter KV not configured (CF_ACCOUNT_ID / "
                       "NEWSLETTER_KV_NAMESPACE_ID / CF_KV_API_TOKEN) — "
                       "skipping newsletter sources")
        return None
    return {"account_id": account_id, "namespace_id": namespace_id, "token": token}


def _kv_list_keys(auth: dict, prefix: str = "nl:") -> List[dict]:
    """List KV keys (with metadata), cursor-paginated."""
    url = (f"{CF_API_BASE}/accounts/{auth['account_id']}/storage/kv/"
           f"namespaces/{auth['namespace_id']}/keys")
    headers = {"Authorization": f"Bearer {auth['token']}"}
    keys: List[dict] = []
    cursor = None
    while True:
        params = {"limit": 1000, "prefix": prefix}
        if cursor:
            params["cursor"] = cursor
        response = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        keys.extend(data.get("result") or [])
        cursor = (data.get("result_info") or {}).get("cursor")
        if not cursor:
            break
    return keys


def _kv_get_value(auth: dict, key: str) -> bytes:
    url = (f"{CF_API_BASE}/accounts/{auth['account_id']}/storage/kv/"
           f"namespaces/{auth['namespace_id']}/values/{requests.utils.quote(key, safe='')}")
    response = requests.get(
        url, headers={"Authorization": f"Bearer {auth['token']}"}, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.content


# === Email parsing ===

def _key_age_days(key: str) -> Optional[float]:
    """Key format nl:<ISO timestamp>:<id> — age in days, None if unparsable."""
    try:
        iso = key.split(":", 1)[1].rsplit(":", 1)[0]
        from datetime import datetime, timezone
        received = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - received).total_seconds() / 86400
    except (IndexError, ValueError):
        return None


def _sender_config(from_header: str) -> Optional[dict]:
    """First matching sender config; None for unknown or blocked senders."""
    sender = (from_header or "").lower()
    for cfg in NEWSLETTER_SENDERS:
        if cfg["match"].lower() in sender:
            return cfg if cfg["name"] else None
    return None


def _email_body_html(raw_mime: bytes) -> str:
    """Extract the HTML (or plain-text) body from a raw MIME message."""
    message = email.message_from_bytes(raw_mime, policy=email.policy.default)
    body = message.get_body(preferencelist=("html", "plain"))
    if body is None:
        return ""
    content = body.get_content()
    # Drop style/script blocks — pure noise for extraction, big token savings
    content = re.sub(r"<(style|script)[\s\S]*?</\1>", " ", content, flags=re.IGNORECASE)
    return content


# === Link hygiene ===

def _strip_tracking_params(url: str) -> str:
    parts = urlparse(url)
    params = [(k, v) for k, v in parse_qsl(parts.query)
              if not k.lower().startswith(("utm_", "mc_", "ck_"))]
    return urlunparse(parts._replace(query=urlencode(params)))


def _resolve_url(url: str) -> str:
    """Unwrap tracking redirects and strip campaign params. Never raises."""
    try:
        host = urlparse(url).netloc
        if host and _TRACKING_HOST_RE.search(host):
            response = requests.get(
                url, timeout=_TIMEOUT, allow_redirects=True, stream=True,
                headers={"User-Agent": Config.USER_AGENT})
            response.close()
            url = response.url
        return _strip_tracking_params(url)
    except Exception as e:
        logger.debug(f"Redirect resolution failed for {url}: {e}")
        return _strip_tracking_params(url)


# === Claude extraction ===

def _extract_items(html: str, newsletter: str, subject: str) -> List[dict]:
    """Ask Claude for the articles linked in one newsletter email."""
    from src.summarizer import get_client, cost_tracker

    prompt = f"""This is one issue of the "{newsletter}" gaming newsletter (subject: "{subject}").
Extract the news/article items it links to.

Rules:
- Only actual news or article links (game releases, industry news, analysis pieces).
- Skip ads, sponsor slots, event/job listings, social links, subscription management.
- Max {_MAX_ITEMS_PER_EMAIL} items, most newsworthy first.
- Reply with ONLY a JSON array, no prose: [{{"url": "...", "title": "...", "summary": "1-2 sentence gist"}}]
- If the email has no article links, reply with [].

Email HTML:
{html[:_MAX_EMAIL_CHARS]}"""

    client = get_client()
    response = client.messages.create(
        model=Config.MODEL_EXTRACT,
        max_tokens=3000,
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": prompt}],
    )
    cost_tracker.add_usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        model=Config.MODEL_EXTRACT,
    )

    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    text = _FENCE_RE.sub("", text).strip()
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"[newsletter:{newsletter}] Claude returned non-JSON, skipping email")
        return []
    if not isinstance(items, list):
        return []

    clean = []
    for item in items[:_MAX_ITEMS_PER_EMAIL]:
        url = (item.get("url") or "").strip() if isinstance(item, dict) else ""
        title = (item.get("title") or "").strip() if isinstance(item, dict) else ""
        if not url.startswith("http") or not title or _JUNK_URL_RE.search(url):
            continue
        resolved = _resolve_url(url)
        if _JUNK_URL_RE.search(resolved):
            continue
        clean.append({
            "url": resolved,
            "title": title,
            "summary": (item.get("summary") or "").strip(),
        })
    return clean


# === Inbox load (shared across collectors, once per run) ===

def _load_inbox(since_days: float = None) -> Dict[str, List[dict]]:
    """Fetch and parse recent newsletter emails, grouped by sender name."""
    global _inbox
    if _inbox is not None:
        return _inbox
    _inbox = {}

    if since_days is None:
        since_days = Config.NEWSLETTER_SINCE_DAYS

    auth = _kv_auth()
    if auth is None:
        return _inbox

    keys = _kv_list_keys(auth)
    recent = [k for k in keys
              if (_key_age_days(k.get("name", "")) or since_days + 1) <= since_days]
    logger.info(f"[newsletter] {len(recent)}/{len(keys)} inbox emails within "
                f"{since_days}-day window")

    for entry in recent:
        meta = entry.get("metadata") or {}
        from_header = meta.get("from", "")
        subject = meta.get("subject", "(no subject)")

        cfg = _sender_config(from_header)
        if cfg is None:
            logger.info(f"[newsletter] Skipping mail from unlisted/blocked "
                        f"sender: {from_header!r} ({subject[:60]!r})")
            continue

        try:
            raw = _kv_get_value(auth, entry["name"])
            html = _email_body_html(raw)
            if not html.strip():
                logger.warning(f"[newsletter:{cfg['name']}] Empty body: {subject[:60]!r}")
                continue
            items = _extract_items(html, cfg["name"], subject)
            time.sleep(Config.API_RATE_LIMIT_SECONDS)
        except Exception as e:
            logger.error(f"[newsletter:{cfg['name']}] Failed to process "
                         f"{subject[:60]!r}: {e}")
            continue

        bucket = _inbox.setdefault(cfg["name"], [])
        for item in items:
            item["email_subject"] = subject
            item["email_date"] = meta.get("date")
            bucket.append(item)
        logger.info(f"[newsletter:{cfg['name']}] {len(items)} items from "
                    f"{subject[:60]!r}")

    return _inbox


def _reset_inbox_cache():
    """Test helper / scheduler hook: force a fresh KV read next run."""
    global _inbox
    _inbox = None


# === Collector ===

class NewsletterCollector(BaseCollector):
    """Collects articles linked from one subscribed newsletter."""

    source_type = "newsletter"

    def __init__(self, name: str):
        self.source_name = name
        self._items: Dict[str, dict] = {}

    def discover(self, limit: int = 20) -> List[str]:
        try:
            inbox = _load_inbox()
        except Exception as e:
            logger.error(f"[newsletter:{self.source_name}] Inbox load failed: {e}")
            return []

        urls = []
        for item in inbox.get(self.source_name, []):
            if item["url"] in self._items:
                continue
            self._items[item["url"]] = item
            urls.append(item["url"])
            if len(urls) >= limit:
                break
        logger.info(f"[newsletter:{self.source_name}] Discovered {len(urls)} items")
        return urls

    def collect(self, url: str) -> Optional[CollectedItem]:
        item = self._items.get(url)
        if item is None:
            logger.warning(f"[newsletter:{self.source_name}] Item not in cache, "
                           f"skipping: {url}")
            return None

        return CollectedItem(
            url=item["url"],
            title=item["title"],
            date=item.get("email_date"),
            author=f"{self.source_name} newsletter",
            content=item.get("summary") or item["title"],
            image_url=None,
            source_type="newsletter",
            source_name=self.source_name,
            content_id=None,
        )


def get_newsletter_collectors() -> List[NewsletterCollector]:
    """One collector per configured (non-blocked) sender."""
    names = [cfg["name"] for cfg in NEWSLETTER_SENDERS if cfg["name"]]
    return [NewsletterCollector(name) for name in names]
