"""
Weekly digest generator — composes an English HTML blog post FOR GAMERS
from the top-scored articles of the last N days.

Sections (empty ones omitted):
  🔥 Play this week
  ⏰ Mark your calendar
  🕹️ Coming soon & worth your money (out-now releases from the past week first)
  🏆 What to watch
  💸 Deals worth grabbing
  ⚠️ Don't get burned

Output saved to data/digests/YYYY-MM-DD-digest.html.
"""

import json
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.config import Config
from src.database import init_db, get_top_scored_articles, get_recent_articles

logger = logging.getLogger(__name__)

DEFAULT_SINCE_DAYS = 7
DEFAULT_TOP_N = 25

CLOSING_LINE = (
    '<p><em>See you next week — same time, same place, '
    '100% of your screen still visible.</em></p>'
)

DIGEST_SECTIONS = [
    "🔥 Play this week",
    "⏰ Mark your calendar",
    "🕹️ Coming soon & worth your money",
    "🏆 What to watch",
    "💸 Deals worth grabbing",
    "⚠️ Don't get burned",
]

# Keyword heuristic for sale/discount/free-promo articles (💸 section).
# Matches: sale, deal(s), discount(ed), price drop/cut, "N% off",
# free for a limited time / temporarily free / goes free, freebie.
DEAL_KEYWORDS = re.compile(
    r"(?i)(?:"
    r"\bsales?\b|\bdeals?\b|\bdiscount(?:ed|s)?\b|"
    r"\bprice\s+(?:drop|cut)s?\b|"
    r"\d+\s*%\s*off\b|\bpercent\s+off\b|"
    r"\bfree\s+for\s+a\s+limited\s+time\b|\btemporarily\s+free\b|"
    r"\b(?:goes|gone|now)\s+free\b|\bfreebies?\b"
    r")"
)

MAX_DEAL_ITEMS = 8

DIGEST_PROMPT = """You are writing a weekly mobile gaming digest blog post FOR GAMERS.
Editorial rule: value = what a player can DO — play something, watch something, avoid a scam or bad purchase, save money. NEVER industry/dev/business analysis, never self-promotion.

Compose an ENGLISH HTML blog post fragment (no <html>, <head> or <body> tags) from the news items below.

Structure (match it exactly):
1. Open with one italic intro line: <p><em>Your weekly briefing on what actually matters in mobile gaming — what to play, what to watch, and what to avoid.</em></p> (you may vary the wording slightly, keep it one line).
2. Group items into these <h2> sections, in this order, OMITTING any section that would be empty:
   - 🔥 Play this week — content that is live NOW (launches, seasons, collabs, events players can jump into)
   - ⏰ Mark your calendar — dated things players of specific games must act on (shutdowns, deadlines, limited-time endings)
   - 🕹️ Coming soon & worth your money — BOTH games RELEASED in the past 7 days ("out now") AND upcoming releases, pre-registrations, betas. List the out-now releases FIRST, then the coming-soon items.
   - 🏆 What to watch — esports, tournaments, streams, big broadcasts
   - 💸 Deals worth grabbing — mobile game sales, discounts, price drops, limited-time free games. Prefer items marked [DEAL]. Always include the price when known (e.g. "$4.99 → free", "60% off"). Only real, current deals — omit this section entirely if there are none.
   - ⚠️ Don't get burned — scams, fake apps, broken purchases, warnings
3. Each section is a <ul> of <li> items. Each <li>: starts with a <strong>punchy hook</strong>, then 1-2 punchy sentences a player cares about (what/when/why act), and ends with an <a href="...">source link</a> using the item's URL. Use the source name or a short action phrase as link text.
4. Tone: energetic, direct, player-to-player. Short sentences. Concrete dates and names. No corporate speak, no hype filler.
5. Skip items with no player value (pure industry/business news). Merge duplicate stories into one item (link the best source).
6. End the post with exactly this line: {closing_line}

News items (title | source | date | url | notes; [DEAL] marks sale/discount candidates):
{items}

Reply with ONLY the HTML fragment. No markdown fences, no commentary."""

EXCERPT_SUFFIX = "Your 5-minute catch-up. →"

EXCERPT_PROMPT = """Below is this week's mobile gaming digest (HTML). Write a click-worthy excerpt for the blog listing page: 1-2 punchy sentences that name the single biggest story and tease the rest. Written FOR GAMERS — what they can play/watch/save, no corporate speak.

The excerpt MUST end with exactly: {suffix}

Digest:
{body}

Reply with ONLY the excerpt text (plain text, no HTML tags, no quotes)."""


class DigestError(Exception):
    """Base exception for digest generation errors."""
    pass


def is_deal_article(article: dict) -> bool:
    """Heuristic: does the title/content indicate a sale/discount/free promo?"""
    text = (
        f"{article.get('title', '')} "
        f"{(article.get('summary') or article.get('content') or '')[:500]}"
    )
    return bool(DEAL_KEYWORDS.search(text))


def find_deal_articles(
    since_days: int, db_path: str, exclude_urls: set = None, limit: int = MAX_DEAL_ITEMS
) -> List[dict]:
    """
    Find recent sale/discount/free-promo articles (keyword heuristic) —
    especially Reddit sale threads and site deal roundups — that aren't
    already in the digest selection.
    """
    exclude_urls = exclude_urls or set()
    deals = []
    for article in get_recent_articles(days=since_days, db_path=db_path):
        if article.get('url') in exclude_urls:
            continue
        if is_deal_article(article):
            deals.append(article)
            if len(deals) >= limit:
                break
    return deals


def _plausible_release_date(release_date, article_date) -> bool:
    """Reject extracted release dates that fall before the article announcing them.

    Small models routinely stamp the wrong year on a bare "September 5-6",
    defaulting to a year they know rather than the article's. A premiere dated
    before its own announcement is such a slip, and a wrong date in the
    calendar section is a mistake readers can see.
    """
    if not release_date or not article_date:
        return True

    text = str(release_date)
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', text)
    if not match:
        return True  # vague forms like "2026 Q4" — pass through untouched

    try:
        released = datetime.fromisoformat(match.group(0)).date()
        published = datetime.fromisoformat(
            str(article_date).replace('Z', '+00:00')
        ).date()
    except (ValueError, TypeError):
        return True

    # A day of slack absorbs timezone differences between feed and article.
    return (published - released).days <= 1


def _format_facts(article: dict) -> str:
    """Compact tag of extracted facts, e.g. '[launch; out 2026-08-14; iOS, Android]'.

    Release dates and event types drive the calendar/coming-soon sections, so
    handing them over explicitly beats making the model mine them from prose.
    """
    raw = article.get('entities')
    if not raw:
        return ''
    try:
        facts = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return ''
    if not isinstance(facts, dict):
        return ''

    parts = []
    if facts.get('event_type'):
        parts.append(str(facts['event_type']))
    if facts.get('release_date'):
        if _plausible_release_date(facts['release_date'], article.get('date')):
            parts.append(f"out {facts['release_date']}")
        else:
            logger.info(
                f"Dropped implausible release_date {facts['release_date']} "
                f"(article dated {article.get('date')})"
            )
    if facts.get('price'):
        parts.append(str(facts['price']))
    platforms = facts.get('platforms')
    if isinstance(platforms, list) and platforms:
        parts.append(', '.join(str(p) for p in platforms[:3]))
    return f"[{'; '.join(parts)}] " if parts else ''


def _format_items(articles: List[dict]) -> str:
    """Format article rows into compact prompt lines ([DEAL] marks sale items)."""
    lines = []
    for article in articles:
        snippet = (article.get('summary') or article.get('content') or '')
        snippet = re.sub(r'\s+', ' ', snippet).strip()[:400]
        deal_tag = '[DEAL] ' if is_deal_article(article) else ''
        lines.append(
            f"- {deal_tag}{_format_facts(article)}{article.get('title', 'Untitled')} | "
            f"{article.get('source_name', 'unknown')} ({article.get('source_type', '')}) | "
            f"{article.get('date') or 'no date'} | "
            f"{article.get('url', '')} | "
            f"{snippet}"
        )
    return '\n'.join(lines)


def _strip_markdown_fences(text: str) -> str:
    """Remove ```html ... ``` fences if the model wrapped its output."""
    text = text.strip()
    text = re.sub(r'^```(?:html)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def compose_digest_html(articles: List[dict]) -> str:
    """Have Claude compose the digest HTML from scored articles."""
    from src.summarizer import get_client, cost_tracker

    client = get_client()
    prompt = DIGEST_PROMPT.format(
        closing_line=CLOSING_LINE,
        items=_format_items(articles),
    )

    logger.info(f"Composing digest from {len(articles)} articles...")
    response = client.messages.create(
        model=Config.MODEL_DIGEST,
        # adaptive thinking (Sonnet 5 default) improves composition quality;
        # headroom covers thinking + the HTML itself
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    cost_tracker.add_usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        model=Config.MODEL_DIGEST,
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    html = _strip_markdown_fences(text)
    if not html:
        raise DigestError("AI returned an empty digest")

    # Mandatory closing line — append if the model forgot it
    if CLOSING_LINE not in html:
        html = html.rstrip() + '\n' + CLOSING_LINE + '\n'

    return html


def get_digest_output_dir() -> Path:
    """Directory where digests are saved (data/digests, next to the DB)."""
    return Config.DATABASE_FULL_PATH.parent / 'digests'


def generate_digest(
    since_days: int = DEFAULT_SINCE_DAYS,
    top_n: int = DEFAULT_TOP_N,
    db_path: str = None,
    output_dir: Path = None,
) -> Path:
    """
    Generate the weekly digest HTML file.

    Selects top-scored articles from the last `since_days` days (falls back to
    most recent articles if nothing has been scored yet), composes the post
    with Claude, and saves it to data/digests/YYYY-MM-DD-digest.html.

    Returns:
        Path to the saved digest file.
    """
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)
    if output_dir is None:
        output_dir = get_digest_output_dir()

    init_db(db_path)

    articles = get_top_scored_articles(days=since_days, limit=top_n, db_path=db_path)
    if not articles:
        logger.warning(
            "No scored articles found — falling back to most recent articles. "
            "Run the scorer first (pipeline --score) for better selection."
        )
        articles = get_recent_articles(days=since_days, db_path=db_path)[:top_n]

    if not articles:
        raise DigestError(
            f"No articles from the last {since_days} days — nothing to digest. "
            "Run a scrape first (pipeline --all)."
        )

    # Add deal candidates (sales/discounts/free promos) missed by top-N scoring
    deal_articles = find_deal_articles(
        since_days, db_path, exclude_urls={a.get('url') for a in articles}
    )
    if deal_articles:
        logger.info(f"Including {len(deal_articles)} deal candidate(s) for 💸 section")
        articles = articles + deal_articles

    html = compose_digest_html(articles)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-digest.html"
    output_path = output_dir / filename
    output_path.write_text(html, encoding='utf-8')

    logger.info(f"Digest saved: {output_path} ({len(html)} chars, {len(articles)} articles)")
    return output_path


def compose_excerpt(body_html: str) -> str:
    """
    Have Claude write a 1-2 sentence click-worthy excerpt for the digest
    (biggest story + teaser). Always ends with EXCERPT_SUFFIX.

    Falls back to a static excerpt if the AI is unavailable — never raises.
    """
    fallback = (
        "The week's biggest mobile gaming news — what to play, what to watch, "
        f"and the deals worth grabbing. {EXCERPT_SUFFIX}"
    )

    try:
        from src.summarizer import get_client, cost_tracker

        client = get_client()
        prompt = EXCERPT_PROMPT.format(suffix=EXCERPT_SUFFIX, body=body_html[:6000])
        response = client.messages.create(
            model=Config.MODEL_SUMMARIZE,
            max_tokens=200,
            # short excerpt: no thinking needed, small model
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        cost_tracker.add_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=Config.MODEL_SUMMARIZE,
        )
        excerpt = next((b.text for b in response.content if b.type == "text"), "").strip().strip('"')
        if not excerpt:
            return fallback
        if not excerpt.endswith(EXCERPT_SUFFIX):
            excerpt = excerpt.rstrip() + ' ' + EXCERPT_SUFFIX
        return excerpt
    except Exception as e:
        logger.warning(f"Excerpt composition failed ({e}) — using fallback excerpt")
        return fallback


def find_latest_digest(output_dir: Path = None) -> Optional[Path]:
    """Find the most recent digest file (by filename date)."""
    if output_dir is None:
        output_dir = get_digest_output_dir()
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return None
    digests = sorted(output_dir.glob('*-digest.html'))
    return digests[-1] if digests else None
