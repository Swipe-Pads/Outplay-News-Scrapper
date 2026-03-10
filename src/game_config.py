"""
Game configuration loader.

Reads per-game YAML config files from the games/ directory.
Each game config specifies sources (Reddit, YouTube, web, etc.),
metadata, and scraping parameters.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


def _get_games_dir() -> Path:
    """Get the games config directory."""
    return Path(__file__).parent.parent / "games"


def load_game_config(slug: str) -> Optional[dict]:
    """
    Load a single game configuration by slug.

    Args:
        slug: Game identifier (e.g., "cod-mobile"). Matches filename.

    Returns:
        Parsed YAML config dict, or None if not found.
    """
    games_dir = _get_games_dir()

    for ext in (".yaml", ".yml"):
        config_path = games_dir / f"{slug}{ext}"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    config["_slug"] = slug
                    config["_path"] = str(config_path)
                    logger.info(f"Loaded game config: {slug}")
                    return config
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse {config_path}: {e}")
                return None
            except Exception as e:
                logger.error(f"Failed to load {config_path}: {e}")
                return None

    logger.warning(f"No config found for game: {slug}")
    return None


def load_all_games() -> List[dict]:
    """
    Load all game configurations from the games/ directory.

    Returns:
        List of parsed game config dicts.
    """
    games_dir = _get_games_dir()
    configs = []

    if not games_dir.exists():
        logger.warning(f"Games directory not found: {games_dir}")
        return configs

    for path in sorted(games_dir.glob("*.y*ml")):
        slug = path.stem
        config = load_game_config(slug)
        if config:
            configs.append(config)

    logger.info(f"Loaded {len(configs)} game configurations")
    return configs


def get_sources_by_priority(config: dict) -> List[dict]:
    """
    Get sources from a game config, sorted by priority (P0 first).

    Args:
        config: Parsed game configuration dict.

    Returns:
        List of source dicts sorted by priority.
    """
    sources = config.get("sources", [])
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(
        sources,
        key=lambda s: priority_order.get(s.get("priority", "P3"), 99),
    )


def get_game_display_name(config: dict) -> str:
    """Get human-readable game name from config."""
    return config.get("name", config.get("_slug", "Unknown Game"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    configs = load_all_games()
    for c in configs:
        name = get_game_display_name(c)
        sources = get_sources_by_priority(c)
        print(f"\n{name} ({c['_slug']})")
        for s in sources:
            print(f"  [{s.get('priority', '?')}] {s.get('type')}: {s.get('name', s.get('subreddit', s.get('channel_id', '?')))}")
