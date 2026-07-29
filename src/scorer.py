"""
Article importance scorer — rates articles 0-100 for the weekly gamer digest.

Combines four signals:
  (a) quantitative signals when present (reddit score, engagement counts)
  (b) cross-source clustering (same story covered by 2+ sources = strong boost)
  (c) freshness decay (older news matters less)
  (d) AI "gamer value" score via Claude (0-10): actionability for players and
      scale of player impact. Industry/business/dev news scores low unless it
      changes what players should do.

Scores are persisted to the `importance_score` column (see database.init_db).
"""

import re
import json
import math
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.config import Config
from src.database import init_db, get_recent_articles, update_article_score

logger = logging.getLogger(__name__)

# Weights (subtotal 0-100, then multiplied by freshness factor)
AI_WEIGHT = 6.0            # ai score 0-10 -> 0-60 points
QUANT_WEIGHT = 15.0        # quantitative signal 0-1 -> 0-15 points
CLUSTER_BONUS_2 = 15.0     # story covered by 2 sources
CLUSTER_BONUS_3 = 25.0     # story covered by 3+ sources
NEUTRAL_AI_SCORE = 5       # fallback when AI scoring unavailable

TITLE_SIMILARITY_THRESHOLD = 0.5
FRESHNESS_HALF_LIFE_DAYS = 3.0
FRESHNESS_FLOOR = 0.4

_STOPWORDS = {
    'a', 'an', 'and', 'the', 'is', 'are', 'to', 'of', 'in', 'on', 'for',
    'with', 'at', 'by', 'from', 'this', 'that', 'its', 'it', 'as', 'be',
    'you', 'your', 'how', 'what', 'why', 'new', 'now', 'here',
}


class ScoringError(Exception):
    """Base exception for scoring errors."""
    pass


# === (b) Cross-source clustering ===

def normalize_title(title: str) -> set:
    """Tokenize a title into a set of lowercase keywords (stopwords removed)."""
    if not title:
        return set()
    tokens = re.findall(r"[a-z0-9]+", title.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def title_similarity(title_a: str, title_b: str) -> float:
    """Jaccard similarity between two titles' keyword sets (0.0-1.0)."""
    a, b = normalize_title(title_a), normalize_title(title_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_articles(articles: List[dict]) -> List[int]:
    """
    Greedy title-similarity clustering.

    Returns a list of cluster sizes aligned with `articles` — cluster_sizes[i]
    is how many articles (across sources) tell the same story as articles[i].
    """
    n = len(articles)
    cluster_ids = [-1] * n
    next_cluster = 0

    for i in range(n):
        if cluster_ids[i] != -1:
            continue
        cluster_ids[i] = next_cluster
        for j in range(i + 1, n):
            if cluster_ids[j] != -1:
                continue
            sim = title_similarity(
                articles[i].get('title', ''), articles[j].get('title', '')
            )
            if sim >= TITLE_SIMILARITY_THRESHOLD:
                cluster_ids[j] = next_cluster
        next_cluster += 1

    counts: Dict[int, int] = {}
    for cid in cluster_ids:
        counts[cid] = counts.get(cid, 0) + 1
    return [counts[cid] for cid in cluster_ids]


def cluster_bonus(cluster_size: int) -> float:
    """Points awarded for cross-source coverage of the same story."""
    if cluster_size >= 3:
        return CLUSTER_BONUS_3
    if cluster_size == 2:
        return CLUSTER_BONUS_2
    return 0.0


# === (c) Freshness decay ===

def _parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-ish date string into an aware UTC datetime."""
    if not value:
        return None
    text = str(value).strip().replace('Z', '+00:00')
    for parser in (
        lambda s: datetime.fromisoformat(s),
        lambda s: datetime.strptime(s, '%Y-%m-%d %H:%M:%S'),
        lambda s: datetime.strptime(s, '%Y-%m-%d'),
    ):
        try:
            dt = parser(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def freshness_factor(article: dict, now: datetime = None) -> float:
    """
    Exponential decay multiplier in [FRESHNESS_FLOOR, 1.0].

    Uses article publish date, falls back to scraped_at; unknown dates get a
    slightly punitive neutral value.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    published = _parse_date(article.get('date')) or _parse_date(article.get('scraped_at'))
    if published is None:
        return 0.7

    age_days = max(0.0, (now - published).total_seconds() / 86400.0)
    decay = math.pow(0.5, age_days / FRESHNESS_HALF_LIFE_DAYS)
    return max(FRESHNESS_FLOOR, decay)


# === (a) Quantitative signals ===

def quantitative_signal(article: dict) -> float:
    """
    Normalize available engagement signals to 0.0-1.0.

    Uses reddit score / engagement counts when present in the article dict;
    otherwise falls back to weak content-quality proxies (length, image).
    """
    # Explicit engagement numbers (log-scaled, 1000+ saturates)
    for key in ('reddit_score', 'score', 'engagement', 'view_count', 'upvotes'):
        value = article.get(key)
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            return 0.0
        return min(1.0, math.log10(1 + value) / 3.0)

    # Weak proxies when no engagement data exists
    signal = 0.0
    content = article.get('content') or ''
    if len(content) > 500:
        signal += 0.3
    elif len(content) > 100:
        signal += 0.15
    if article.get('image_path') or article.get('image_url'):
        signal += 0.1
    if article.get('date'):
        signal += 0.1
    return min(1.0, signal)


# === (d) AI gamer-value score ===

AI_SCORING_PROMPT = """You are scoring mobile gaming news items for a weekly digest written FOR GAMERS.
Value = what a player can DO with the news: play something new or updated, watch an event or tournament, avoid a scam or a bad purchase, save money.

Score each item 0-10 for gamer value, based on actionability for players and the scale of player impact:
- 9-10: major playable/watchable impact for many players (big game launch, major season/collab going live, game shutdown players must act on, huge event)
- 6-8: clearly actionable for a meaningful segment of players (pre-registrations, betas, notable releases, warnings about scams or broken purchases)
- 3-5: mildly interesting to players, low urgency
- 0-2: industry/business/developer/funding/hiring/self-promotion news that does NOT change what players should do

Items:
{items}

Reply with ONLY a JSON array of integers (one score per item, same order). No other text."""


def _parse_ai_scores(text: str, expected: int) -> List[int]:
    """Extract a JSON array of ints from the model response; neutral fallback."""
    match = re.search(r'\[[^\[\]]*\]', text, re.DOTALL)
    if match:
        try:
            raw = json.loads(match.group(0))
            scores = [max(0, min(10, int(round(float(x))))) for x in raw]
            if len(scores) == expected:
                return scores
            logger.warning(
                f"AI returned {len(scores)} scores, expected {expected} — using neutral fallback"
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse AI scores: {e}")
    else:
        logger.warning("No JSON array found in AI scoring response")
    return [NEUTRAL_AI_SCORE] * expected


def ai_gamer_value_scores(articles: List[dict], batch_size: int = 20) -> List[int]:
    """
    Score articles 0-10 for gamer value using Claude (batched to save tokens).

    Raises SummarizationError/APIKeyError from the summarizer module on
    unrecoverable API problems — callers may catch and fall back to neutral.
    """
    from src.summarizer import get_client, cost_tracker

    client = get_client()
    all_scores: List[int] = []

    for start in range(0, len(articles), batch_size):
        chunk = articles[start:start + batch_size]
        lines = []
        for idx, article in enumerate(chunk, 1):
            snippet = (article.get('summary') or article.get('content') or '')
            snippet = re.sub(r'\s+', ' ', snippet)[:300]
            lines.append(f"{idx}. {article.get('title', 'Untitled')} — {snippet}")

        prompt = AI_SCORING_PROMPT.format(items='\n'.join(lines))

        response = client.messages.create(
            model=Config.MODEL_SCORE,
            max_tokens=300,
            # cheap batch scoring: no thinking, small model
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        cost_tracker.add_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=Config.MODEL_SCORE,
        )

        text = next(b.text for b in response.content if b.type == "text")
        all_scores.extend(_parse_ai_scores(text, len(chunk)))

    return all_scores


# === Combined scoring ===

def compute_scores(articles: List[dict], use_ai: bool = True) -> List[float]:
    """
    Compute 0-100 importance scores for a batch of articles.

    Returns a list of scores aligned with `articles`.
    """
    if not articles:
        return []

    cluster_sizes = cluster_articles(articles)

    if use_ai:
        from src.summarizer import SummarizationError, APIKeyError
        try:
            ai_scores = ai_gamer_value_scores(articles)
        except (SummarizationError, APIKeyError) as e:
            logger.warning(f"AI scoring unavailable ({e}) — using neutral AI scores")
            ai_scores = [NEUTRAL_AI_SCORE] * len(articles)
    else:
        ai_scores = [NEUTRAL_AI_SCORE] * len(articles)

    now = datetime.now(timezone.utc)
    scores = []
    for article, ai_score, cluster_size in zip(articles, ai_scores, cluster_sizes):
        subtotal = (
            ai_score * AI_WEIGHT
            + quantitative_signal(article) * QUANT_WEIGHT
            + cluster_bonus(cluster_size)
        )
        score = subtotal * freshness_factor(article, now)
        scores.append(round(max(0.0, min(100.0, score)), 1))

    return scores


def score_recent_articles(
    days: int = 7,
    db_path: str = None,
    use_ai: bool = True,
) -> Dict[str, int]:
    """
    Score all articles from the last N days and persist importance_score.

    Returns stats dict: {'total', 'scored', 'failed'}.
    """
    if db_path is None:
        db_path = str(Config.DATABASE_FULL_PATH)

    init_db(db_path)
    articles = get_recent_articles(days=days, db_path=db_path)
    stats = {'total': len(articles), 'scored': 0, 'failed': 0}

    if not articles:
        logger.info(f"No articles from the last {days} days to score")
        return stats

    logger.info(f"Scoring {len(articles)} articles from the last {days} days...")
    scores = compute_scores(articles, use_ai=use_ai)

    for article, score in zip(articles, scores):
        try:
            update_article_score(article['url'], score, db_path)
            stats['scored'] += 1
        except Exception as e:
            logger.error(f"Failed to save score for {article.get('url')}: {e}")
            stats['failed'] += 1

    logger.info(f"Scoring complete: {stats['scored']} scored, {stats['failed']} failed")
    return stats
