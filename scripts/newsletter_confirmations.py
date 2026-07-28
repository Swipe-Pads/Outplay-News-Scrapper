#!/usr/bin/env python3
"""
List double-opt-in confirmation links from the newsletter inbox KV.

Newsletter signups mail a "confirm your subscription" message to the
news.outplay.game address; the newsletter-inbox Worker stores the raw MIME
in KV. This script scans recent KV entries and prints any links that look
like opt-in confirmations, so they can be clicked from the Actions log
(no local Cloudflare KV credentials exist — see docs in the repo).

Env: CF_ACCOUNT_ID, CF_KV_API_TOKEN, NEWSLETTER_KV_NAMESPACE_ID,
     SINCE_DAYS (optional, default 3).
"""

import email
import email.policy
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

CF_API_BASE = "https://api.cloudflare.com/client/v4"
_TIMEOUT = 20

ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"].strip()
NAMESPACE_ID = os.environ["NEWSLETTER_KV_NAMESPACE_ID"].strip()
HEADERS = {"Authorization": f"Bearer {os.environ['CF_KV_API_TOKEN'].strip()}"}
SINCE_DAYS = float(os.environ.get("SINCE_DAYS") or 3)


def _raise_with_body(response):
    """CF error bodies carry the actual reason — surface them before raising."""
    if response.status_code >= 400:
        print(f"CF API {response.status_code}: {response.text[:500]}",
              file=sys.stderr)
    response.raise_for_status()


URL_RE = re.compile(r"""https?://[^\s"'<>)\]]+""")
CONFIRM_RE = re.compile(r"confirm|verif|activat|opt[-_]?in|validate", re.IGNORECASE)
NOT_CONFIRM_RE = re.compile(r"unsubscribe|manage.preferences|privacy|terms", re.IGNORECASE)


def kv_list_keys():
    url = (f"{CF_API_BASE}/accounts/{ACCOUNT_ID}/storage/kv/"
           f"namespaces/{NAMESPACE_ID}/keys")
    keys, cursor = [], None
    while True:
        params = {"limit": 1000, "prefix": "nl:"}
        if cursor:
            params["cursor"] = cursor
        response = requests.get(url, headers=HEADERS, params=params, timeout=_TIMEOUT)
        _raise_with_body(response)
        data = response.json()
        keys.extend(data.get("result") or [])
        cursor = (data.get("result_info") or {}).get("cursor")
        if not cursor:
            return keys


def kv_get_value(key: str) -> bytes:
    url = (f"{CF_API_BASE}/accounts/{ACCOUNT_ID}/storage/kv/"
           f"namespaces/{NAMESPACE_ID}/values/{key}")
    response = requests.get(url, headers=HEADERS, timeout=_TIMEOUT)
    _raise_with_body(response)
    return response.content


def key_timestamp(name: str):
    """Key layout: nl:<received ISO date>:<random hex>."""
    iso = name.removeprefix("nl:").rsplit(":", 1)[0]
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def email_bodies(msg) -> str:
    parts = []
    for part in msg.walk():
        if part.get_content_type() in ("text/html", "text/plain"):
            try:
                parts.append(part.get_content())
            except Exception:
                pass
    return "\n".join(parts)


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=SINCE_DAYS)
    recent = [k for k in kv_list_keys()
              if (ts := key_timestamp(k["name"])) and ts >= cutoff]
    print(f"{len(recent)} email(s) in KV within the last {SINCE_DAYS:g} day(s)")

    with_links = 0
    for key in sorted(recent, key=lambda k: k["name"]):
        msg = email.message_from_bytes(kv_get_value(key["name"]),
                                       policy=email.policy.default)
        sender = msg.get("from", "?")
        subject = msg.get("subject", "?")
        print(f"\n=== {sender}\n    {subject}")

        links = list(dict.fromkeys(URL_RE.findall(email_bodies(msg))))
        confirm = [u.rstrip(".,;")
                   for u in links
                   if CONFIRM_RE.search(u) and not NOT_CONFIRM_RE.search(u)]
        if confirm:
            with_links += 1
            for u in confirm[:5]:
                print(f"    CONFIRM -> {u}")
        else:
            print("    (no confirmation-looking links)")

    print(f"\nDone: {with_links} email(s) with confirmation links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
