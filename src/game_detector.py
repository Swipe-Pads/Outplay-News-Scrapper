"""
Game detection module for auto-tagging articles to games.

Uses the AI summarizer to detect which game(s) an article is about,
then maps to known game slugs in the system.

This enables global news sources (Pocket Gamer, TouchArcade, etc.) to be
automatically tagged to the correct game without per-game source config.
"""

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# Known game names → slug mapping
# This is the canonical mapping used for auto-detection.
# Add new games here as they're added to Strapi.
GAME_ALIASES = {
    "cod-mobile": [
        "call of duty mobile", "call of duty: mobile", "cod mobile", "codm",
        "cod:m", "warzone mobile", "call of duty warzone mobile",
    ],
    "free-fire": [
        "free fire", "garena free fire", "free fire max", "ff max",
        "freefire",
    ],
    "brawl-stars": [
        "brawl stars", "brawlstars",
    ],
    "mobile-legends": [
        "mobile legends", "mobile legends: bang bang", "mlbb",
        "mobile legends bang bang",
    ],
    "pubg-mobile": [
        "pubg mobile", "pubg: mobile", "pubg new state", "bgmi",
        "battlegrounds mobile india", "pubg",
    ],
    "wild-rift": [
        "wild rift", "league of legends: wild rift", "lol wild rift",
        "lol: wild rift", "league wild rift",
    ],
    "genshin-impact": [
        "genshin impact", "genshin",
    ],
    "honkai-star-rail": [
        "honkai star rail", "honkai: star rail", "star rail", "hsr",
    ],
    "clash-royale": [
        "clash royale",
    ],
    "clash-of-clans": [
        "clash of clans", "coc",
    ],
    "apex-legends-mobile": [
        "apex legends mobile", "apex mobile",
    ],
    "valorant": [
        "valorant", "valorant mobile",
    ],
    "diablo-immortal": [
        "diablo immortal",
    ],
}

# Pre-compile regex patterns for fast matching
_GAME_PATTERNS = {}
for slug, aliases in GAME_ALIASES.items():
    # Sort by length (longest first) to match most specific alias
    sorted_aliases = sorted(aliases, key=len, reverse=True)
    # Build regex with word boundaries
    pattern_str = "|".join(re.escape(a) for a in sorted_aliases)
    _GAME_PATTERNS[slug] = re.compile(rf"\b({pattern_str})\b", re.IGNORECASE)


def detect_game(title: str, body: str = "", source_name: str = "") -> Optional[str]:
    """
    Detect which game an article is about based on title and body text.

    Uses keyword matching against known game aliases. Checks title first
    (higher confidence), then body text.

    Args:
        title: Article title.
        body: Article body text (optional, checked if title doesn't match).
        source_name: Source name (can contain game hints like "r/CoDMCompetitive").

    Returns:
        Game slug (e.g., "cod-mobile") or None if no game detected.
    """
    # Combine text for searching (title weighted by checking first)
    combined = f"{title} {source_name}"

    # Check title + source first (high confidence)
    matches = _find_matches(combined)
    if matches:
        # Return highest-confidence match
        return matches[0][0]

    # Check body text (lower confidence, only if title didn't match)
    if body:
        # Only check first 500 chars of body to avoid false positives
        body_matches = _find_matches(body[:500])
        if body_matches:
            return body_matches[0][0]

    return None


def detect_all_games(title: str, body: str = "", source_name: str = "") -> List[str]:
    """
    Detect ALL games mentioned in an article.

    Useful for articles that cover multiple games (e.g., "Best Mobile MOBAs 2026").

    Args:
        title: Article title.
        body: Article body text.
        source_name: Source name.

    Returns:
        List of game slugs mentioned, sorted by confidence (title matches first).
    """
    combined = f"{title} {source_name} {body[:1000] if body else ''}"
    matches = _find_matches(combined)
    # Return unique slugs preserving order
    seen = set()
    result = []
    for slug, _ in matches:
        if slug not in seen:
            seen.add(slug)
            result.append(slug)
    return result


def _find_matches(text: str) -> List[Tuple[str, str]]:
    """
    Find all game matches in text.

    Returns:
        List of (slug, matched_alias) tuples, sorted by match position.
    """
    matches = []

    for slug, pattern in _GAME_PATTERNS.items():
        match = pattern.search(text)
        if match:
            matches.append((slug, match.group(0), match.start()))

    # Sort by position (earlier mention = higher confidence)
    matches.sort(key=lambda m: m[2])

    return [(slug, alias) for slug, alias, _ in matches]


def add_game_alias(slug: str, aliases: List[str]):
    """
    Dynamically add game aliases at runtime.

    Useful for adding games from Strapi without code changes.

    Args:
        slug: Game slug.
        aliases: List of name variants to match.
    """
    GAME_ALIASES[slug] = aliases
    sorted_aliases = sorted(aliases, key=len, reverse=True)
    pattern_str = "|".join(re.escape(a) for a in sorted_aliases)
    _GAME_PATTERNS[slug] = re.compile(rf"\b({pattern_str})\b", re.IGNORECASE)
    logger.info(f"Added game alias: {slug} ({len(aliases)} variants)")


def load_games_from_strapi(strapi_client) -> int:
    """
    Load game names from Strapi and register as detection aliases.

    Queries the Game collection in Strapi and adds each game's name
    and slug as detection aliases. This means adding a game in Strapi
    automatically makes it detectable by the scraper.

    Args:
        strapi_client: Initialised StrapiClient instance.

    Returns:
        Number of games loaded.
    """
    try:
        result = strapi_client._request("GET", "/api/games", params={
            "pagination[pageSize]": 100,
            "fields[0]": "name",
            "fields[1]": "slug",
        })

        games = result.get("data", [])
        count = 0

        for game in games:
            attrs = game.get("attributes", game)
            name = attrs.get("name", "")
            slug = attrs.get("slug", "")

            if name and slug:
                # Don't overwrite existing aliases (they're more comprehensive)
                if slug not in GAME_ALIASES:
                    aliases = [name.lower()]
                    # Also add slug with spaces
                    slug_as_name = slug.replace("-", " ")
                    if slug_as_name != name.lower():
                        aliases.append(slug_as_name)
                    add_game_alias(slug, aliases)
                    count += 1

        logger.info(f"Loaded {count} new games from Strapi (total: {len(GAME_ALIASES)})")
        return count

    except Exception as e:
        logger.error(f"Failed to load games from Strapi: {e}")
        return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test detection
    test_cases = [
        ("New Call of Duty Mobile Season 8 Update", "", ""),
        ("PUBG Mobile and Free Fire compete for players", "", ""),
        ("Best MOBAs for Android 2026", "Mobile Legends and Wild Rift top the charts", ""),
        ("Random tech article", "Nothing about games", ""),
        ("Update patches and fixes", "", "Reddit r/CoDMCompetitive"),
        ("Genshin Impact 5.0 Release Date Confirmed", "", ""),
    ]

    print("Game Detection Test")
    print("=" * 70)
    for title, body, source in test_cases:
        primary = detect_game(title, body, source)
        all_games = detect_all_games(title, body, source)
        print(f"  Title: {title[:50]}")
        print(f"  Primary: {primary or '(none)'}")
        print(f"  All: {all_games or '(none)'}")
        print()
