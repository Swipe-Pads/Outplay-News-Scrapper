"""
Weekly digest generator — composes an English HTML blog post FOR GAMERS
from the top-scored articles of the last N days.

Sections (empty ones omitted):
  🔥 Play this week
  ⏰ Mark your calendar
  🕹️ Coming soon & worth your money
  🏆 What to watch
  ⚠️ Don't get burned

Output saved to data/digests/YYYY-MM-DD-digest.html.
"""

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
    "⚠️ Don't get burned",
]

DIGEST_PROMPT = """You are writing a weekly mobile gaming digest blog post FOR GAMERS.
Editorial rule: value = what a player can DO — play something, watch something, avoid a scam or bad purchase, save money. NEVER industry/dev/business analysis, never self-promotion.

Compose an ENGLISH HTML blog post fragment (no <html>, <head> or <body> tags) from the news items below.

Structure (match it exactly):
1. Open with one italic intro line: <p><em>Your weekly briefing on what actually matters in mobile gaming — what to play, what to watch, and what to avoid.</em></p> (you may vary the wording slightly, keep it one line).
2. Group items into these <h2> sections, in this order, OMITTING any section that would be empty:
   - 🔥 Play this week — content that is live NOW (launches, seasons, collabs, events players can jump into)
   - ⏰ Mark your calendar — dated things players of specific games must act on (shutdowns, deadlines, limited-time endings)
   - 🕹️ Coming soon & worth your money — upcoming releases, pre-registrations, betas, new games worth buying
   - 🏆 What to watch — esports, tournaments, streams, big broadcasts
   - ⚠️ Don't get burned — scams, fake apps, broken purchases, warnings
3. Each section is a <ul> of <li> items. Each <li>: starts with a <strong>punchy hook</strong>, then 1-2 punchy sentences a player cares about (what/when/why act), and ends with an <a href="...">source link</a> using the item's URL. Use the source name or a short action phrase as link text.
4. Tone: energetic, direct, player-to-player. Short sentences. Concrete dates and names. No corporate speak, no hype filler.
5. Skip items with no player value (pure industry/business news). Merge duplicate stories into one item (link the best source).
6. End the post with exactly this line: {closing_line}

News items (title | source | date | url | notes):
{items}

Reply with ONLY the HTML fragment. No markdown fences, no commentary."""


class DigestError(Exception):
    """Base exception for digest generation errors."""
    pass


def _format_items(articles: List[dict]) -> str:
    """Format article rows into compact prompt lines."""
    lines = []
    for article in articles:
        snippet = (article.get('summary') or article.get('content') or '')
        snippet = re.sub(r'\s+', ' ', snippet).strip()[:400]
        lines.append(
            f"- {article.get('title', 'Untitled')} | "
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
        model=Config.CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    cost_tracker.add_usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

    html = _strip_markdown_fences(response.content[0].text)
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

    html = compose_digest_html(articles)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-digest.html"
    output_path = output_dir / filename
    output_path.write_text(html, encoding='utf-8')

    logger.info(f"Digest saved: {output_path} ({len(html)} chars, {len(articles)} articles)")
    return output_path


def find_latest_digest(output_dir: Path = None) -> Optional[Path]:
    """Find the most recent digest file (by filename date)."""
    if output_dir is None:
        output_dir = get_digest_output_dir()
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return None
    digests = sorted(output_dir.glob('*-digest.html'))
    return digests[-1] if digests else None
