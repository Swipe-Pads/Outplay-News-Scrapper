"""
Main orchestrator for the Outplay News Scraper pipeline.

Coordinates the full end-to-end flow:
1. (Optional) Google Trends pulse check → dynamic scraping priorities
2. Scrape global news sources → auto-tag articles to games
3. Scrape per-game sources (Reddit, YouTube, web)
4. Store raw content in SQLite
5. AI-summarize unsummarized articles
6. Push summarized articles to Strapi as drafts
7. Expire old articles in Strapi

Usage:
    python src/orchestrator.py --game cod-mobile        # Single game
    python src/orchestrator.py --all                    # All games
    python src/orchestrator.py --all --trends           # All games with Trends-driven priorities
    python src/orchestrator.py --global-only            # Only scrape global sources
    python src/orchestrator.py --game cod-mobile --dry-run  # No Strapi push
    python src/orchestrator.py --expire                 # Archive expired articles
    python src/orchestrator.py --cleanup                # Delete old drafts
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.database import (
    init_db,
    insert_article,
    article_exists,
    get_unsummarized_articles,
    get_unsynced_articles,
    update_article_summary,
    mark_synced_to_strapi,
    get_article_count,
)
from src.game_config import load_game_config, load_all_games, get_sources_by_priority, get_game_display_name
from src.game_detector import detect_game

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("orchestrator")


# ─── SCRAPER DISPATCH ───────────────────────────────────────────────

def _scrape_reddit_source(source: dict, game_slug: str) -> list:
    """Run Reddit scraper for a single source config."""
    try:
        from src.scrapers.reddit_scraper import RedditScraper
        scraper = RedditScraper()
        posts = scraper.scrape_subreddit(
            subreddit=source["subreddit"],
            flair_filters=source.get("flair_filters"),
            sort=source.get("sort", "hot"),
            time_filter=source.get("time_filter", "day"),
            limit=source.get("limit", 15),
        )
        # Tag with game slug
        for p in posts:
            p["game_slug"] = game_slug
        return posts
    except ValueError as e:
        logger.warning(f"Reddit scraper not configured: {e}")
        return []
    except Exception as e:
        logger.error(f"Reddit scraper error for {source.get('name', '?')}: {e}")
        return []


def _scrape_youtube_source(source: dict, game_slug: str) -> list:
    """Run YouTube scraper for a single source config."""
    try:
        from src.scrapers.youtube_scraper import YouTubeScraper
        scraper = YouTubeScraper()

        if "channel_id" in source:
            videos = scraper.search_channel_videos(
                channel_id=source["channel_id"],
                max_age_days=source.get("max_age_days", 7),
                limit=source.get("limit", 10),
            )
        elif "search_term" in source:
            videos = scraper.get_trending_game_videos(
                game_name=source["search_term"],
                max_age_days=source.get("max_age_days", 7),
                limit=source.get("limit", 10),
            )
        else:
            logger.warning(f"YouTube source missing channel_id or search_term: {source.get('name')}")
            return []

        for v in videos:
            v["game_slug"] = game_slug
        return videos

    except ValueError as e:
        logger.warning(f"YouTube scraper not configured: {e}")
        return []
    except Exception as e:
        logger.error(f"YouTube scraper error for {source.get('name', '?')}: {e}")
        return []


def _scrape_web_source(source: dict, game_slug: str) -> list:
    """Run web scraper for a single source config."""
    try:
        from src.scrapers.web_scraper import WebScraper
        scraper = WebScraper()
        articles = scraper.scrape_listing(
            listing_url=source["url"],
            link_pattern=source.get("link_pattern", r"/news/"),
            limit=source.get("limit", 10),
            source_name=source.get("name"),
            game_slug=game_slug,
        )
        return articles
    except Exception as e:
        logger.error(f"Web scraper error for {source.get('name', '?')}: {e}")
        return []


SCRAPER_DISPATCH = {
    "reddit": _scrape_reddit_source,
    "youtube": _scrape_youtube_source,
    "web": _scrape_web_source,
    "official_blog": _scrape_web_source,
    "wiki": _scrape_web_source,
}


# ─── PIPELINE STAGES ────────────────────────────────────────────────

def scrape_game(game_config: dict) -> dict:
    """
    Run all scrapers for a game and store results in SQLite.

    Returns stats dict with counts.
    """
    slug = game_config.get("_slug", "unknown")
    name = get_game_display_name(game_config)
    db_path = Config.DATABASE_PATH

    logger.info(f"{'='*60}")
    logger.info(f"SCRAPING: {name} ({slug})")
    logger.info(f"{'='*60}")

    init_db(db_path)

    sources = get_sources_by_priority(game_config)
    stats = {"scraped": 0, "stored": 0, "skipped": 0, "errors": 0}

    for source in sources:
        source_type = source.get("type", "unknown")
        source_name = source.get("name", source_type)
        priority = source.get("priority", "P3")

        logger.info(f"  [{priority}] {source_name} ({source_type})")

        scraper_fn = SCRAPER_DISPATCH.get(source_type)
        if not scraper_fn:
            logger.warning(f"  No scraper for type: {source_type}")
            continue

        try:
            items = scraper_fn(source, slug)
            stats["scraped"] += len(items)

            for item in items:
                try:
                    # Check for duplicate
                    if article_exists(item["source_url"], db_path):
                        stats["skipped"] += 1
                        continue

                    # Map ScrapedContent → DB article dict
                    article = {
                        "url": item["source_url"],
                        "title": item.get("title", "Untitled"),
                        "date": item.get("source_published_at"),
                        "author": item.get("original_author"),
                        "content": item.get("body", ""),
                        "image_url": item.get("image_url"),
                        "video_url": item.get("video_url"),
                        "source_name": item.get("source_name", source_name),
                        "content_type": item.get("content_type", "news"),
                        "game_slug": slug,
                    }

                    insert_article(article, db_path)
                    stats["stored"] += 1

                except Exception as e:
                    logger.error(f"  Error storing article: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"  Scraper failed for {source_name}: {e}")
            stats["errors"] += 1

    logger.info(f"  Results: {stats['scraped']} scraped, {stats['stored']} new, "
                f"{stats['skipped']} skipped, {stats['errors']} errors")
    return stats


def scrape_global_sources() -> dict:
    """
    Scrape global gaming news portals and auto-tag articles to games.

    Global sources (Pocket Gamer, TouchArcade, etc.) cover all games.
    Articles are stored with game_slug detected via game_detector.

    Returns stats dict.
    """
    global_config = load_game_config("_global")
    if not global_config:
        logger.info("No _global.yaml config found, skipping global sources")
        return {"scraped": 0, "stored": 0, "skipped": 0, "tagged": 0, "errors": 0}

    db_path = Config.DATABASE_PATH
    init_db(db_path)

    sources = get_sources_by_priority(global_config)
    stats = {"scraped": 0, "stored": 0, "skipped": 0, "tagged": 0, "errors": 0}

    logger.info(f"{'='*60}")
    logger.info(f"SCRAPING: Global News Sources ({len(sources)} sources)")
    logger.info(f"{'='*60}")

    for source in sources:
        source_type = source.get("type", "unknown")
        source_name = source.get("name", source_type)
        priority = source.get("priority", "P3")

        logger.info(f"  [{priority}] {source_name} ({source_type})")

        scraper_fn = SCRAPER_DISPATCH.get(source_type)
        if not scraper_fn:
            logger.warning(f"  No scraper for type: {source_type}")
            continue

        try:
            items = scraper_fn(source, "_global")
            stats["scraped"] += len(items)

            for item in items:
                try:
                    if article_exists(item["source_url"], db_path):
                        stats["skipped"] += 1
                        continue

                    # Auto-detect game from title + body
                    detected_slug = detect_game(
                        title=item.get("title", ""),
                        body=item.get("body", ""),
                        source_name=item.get("source_name", ""),
                    )

                    article = {
                        "url": item["source_url"],
                        "title": item.get("title", "Untitled"),
                        "date": item.get("source_published_at"),
                        "author": item.get("original_author"),
                        "content": item.get("body", ""),
                        "image_url": item.get("image_url"),
                        "video_url": item.get("video_url"),
                        "source_name": item.get("source_name", source_name),
                        "content_type": item.get("content_type", "news"),
                        "game_slug": detected_slug,  # Auto-tagged (or None)
                    }

                    insert_article(article, db_path)
                    stats["stored"] += 1
                    if detected_slug:
                        stats["tagged"] += 1
                        logger.debug(f"    Auto-tagged to: {detected_slug}")

                except Exception as e:
                    logger.error(f"  Error storing article: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"  Scraper failed for {source_name}: {e}")
            stats["errors"] += 1

    logger.info(
        f"  Global results: {stats['scraped']} scraped, {stats['stored']} new, "
        f"{stats['tagged']} auto-tagged, {stats['skipped']} skipped"
    )
    return stats


def run_trends_pulse(game_names: List[str]) -> dict:
    """
    Run Google Trends pulse check and return scraping priorities.

    Returns dict mapping game names to priority configs, or empty dict
    if Trends client is not available.
    """
    try:
        from src.trends_client import get_trends_client
    except ImportError:
        logger.warning("Trends client not available (missing dependencies)")
        return {}

    client = get_trends_client()
    if not client:
        logger.warning("Trends client not configured, using default priorities")
        return {}

    logger.info(f"{'='*60}")
    logger.info(f"GOOGLE TRENDS PULSE CHECK")
    logger.info(f"{'='*60}")

    try:
        priorities = client.get_scraping_priorities(game_names)

        # Log results
        for game, config in priorities.items():
            flag = ""
            if config["priority"] == "high":
                flag = " *** HIGH SPIKE ***"
            elif config["priority"] == "elevated":
                flag = " * SPIKE *"
            logger.info(
                f"  {game:30s}  change={config['change_pct']:+6.1f}%  "
                f"limit={config['limit']}  [{config['priority']}]{flag}"
            )

        quota = client.get_quota_status()
        logger.info(f"  Quota: {quota['requests_used']}/{100} requests, "
                     f"{quota['points_used']}/{10000} points")

        return priorities

    except Exception as e:
        logger.error(f"Trends pulse check failed: {e}")
        return {}


def summarize_unsummarized(game_slug: str = None, limit: int = 50) -> dict:
    """
    AI-summarize articles that don't have summaries yet.

    Returns stats dict.
    """
    db_path = Config.DATABASE_PATH
    stats = {"processed": 0, "success": 0, "failed": 0}

    try:
        from src.summarizer import process_article, get_cost_summary
    except Exception as e:
        logger.error(f"Summarizer not available: {e}")
        return stats

    articles = get_unsummarized_articles(limit, db_path)

    # Filter by game if specified
    if game_slug:
        articles = [a for a in articles if a.get("game_slug") == game_slug]

    if not articles:
        logger.info("No articles to summarize")
        return stats

    logger.info(f"Summarizing {len(articles)} articles...")

    for article in articles:
        stats["processed"] += 1
        try:
            result = process_article(
                title=article["title"],
                content=article.get("content", ""),
                source_name=article.get("source_name", ""),
                game_name=article.get("game_slug", ""),
            )

            if result:
                update_article_summary(article["url"], result, db_path)
                stats["success"] += 1
                logger.info(f"  Summarized: {article['title'][:60]}...")
            else:
                stats["failed"] += 1
                logger.warning(f"  Failed to summarize: {article['title'][:60]}...")

            # Brief pause between API calls
            time.sleep(0.5)

        except Exception as e:
            stats["failed"] += 1
            logger.error(f"  Summarization error: {e}")

    cost = get_cost_summary()
    logger.info(f"Summarization complete: {stats['success']}/{stats['processed']} succeeded")
    logger.info(f"API cost: ${cost['total_cost_usd']:.4f} ({cost['total_tokens']} tokens)")
    return stats


def push_to_strapi(game_slug: str = None, limit: int = 10, dry_run: bool = False) -> dict:
    """
    Push summarized articles to Strapi as drafts.

    Returns stats dict.
    """
    db_path = Config.DATABASE_PATH
    stats = {"pushed": 0, "skipped": 0, "failed": 0, "thumbnails": 0}

    if dry_run:
        logger.info("[DRY RUN] Would push to Strapi, but skipping")
        articles = get_unsynced_articles(limit, db_path)
        if game_slug:
            articles = [a for a in articles if a.get("game_slug") == game_slug]
        for a in articles:
            logger.info(f"  [DRY RUN] Would push: {a['title'][:60]}...")
        stats["pushed"] = len(articles)
        return stats

    try:
        from src.strapi_client import get_strapi_client, StrapiAuthError
    except ImportError:
        logger.error("Strapi client not available")
        return stats

    try:
        client = get_strapi_client()
    except Exception as e:
        logger.error(f"Failed to initialize Strapi client: {e}")
        return stats

    articles = get_unsynced_articles(limit, db_path)
    if game_slug:
        articles = [a for a in articles if a.get("game_slug") == game_slug]

    if not articles:
        logger.info("No articles to push to Strapi")
        return stats

    logger.info(f"Pushing {len(articles)} articles to Strapi...")

    for article in articles:
        try:
            source_url = article["url"]

            # Check if already in Strapi
            existing = client.article_exists(source_url)
            if existing:
                stats["skipped"] += 1
                continue

            # Look up game in Strapi
            game_id = None
            if article.get("game_slug"):
                game = client.get_game_by_slug(article["game_slug"])
                if game:
                    game_id = game.get("id")

            # Build Strapi payload
            strapi_data = {
                "title": article.get("title", "Untitled"),
                "summary": article.get("summary", "")[:150],
                "body": article.get("body_rewritten") or article.get("content", ""),
                "contentType": article.get("content_type", "news"),
                "sourceUrl": source_url,
                "sourceName": article.get("source_name", "Unknown"),
                "originalAuthor": article.get("author"),
                "videoUrl": article.get("video_url"),
                "reviewStatus": "pending",
                "scrapedAt": article.get("scraped_at", datetime.utcnow().isoformat() + "Z"),
                "priority": "normal",
                "relevanceScore": article.get("relevance_score", 0.5),
                "game_id": game_id,
            }

            result = client.create_draft_article(strapi_data)
            strapi_id = result.get("id")

            if strapi_id:
                mark_synced_to_strapi(source_url, strapi_id, db_path)
                stats["pushed"] += 1

                # Upload thumbnail if available
                image_url = article.get("image_url")
                if image_url:
                    thumb_result = client.upload_thumbnail_from_url(image_url, strapi_id)
                    if thumb_result:
                        stats["thumbnails"] += 1

            # Brief pause between API calls
            time.sleep(0.3)

        except Exception as e:
            stats["failed"] += 1
            logger.error(f"  Failed to push article: {e}")

    logger.info(f"Strapi push complete: {stats['pushed']} pushed, "
                f"{stats['skipped']} skipped, {stats['failed']} failed, "
                f"{stats['thumbnails']} thumbnails uploaded")
    return stats


def expire_articles() -> dict:
    """Archive expired articles in Strapi."""
    stats = {"archived": 0}
    try:
        from src.strapi_client import get_strapi_client
        client = get_strapi_client()
        stats["archived"] = client.archive_expired_articles()
    except Exception as e:
        logger.error(f"Expiration failed: {e}")
    return stats


def cleanup_drafts(days: int = 30) -> dict:
    """Delete old draft articles from Strapi."""
    stats = {"deleted": 0}
    try:
        from src.strapi_client import get_strapi_client
        client = get_strapi_client()
        stats["deleted"] = client.cleanup_old_drafts(days)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
    return stats


# ─── MAIN PIPELINE ──────────────────────────────────────────────────

def run_pipeline(
    game_slug: str = None,
    all_games: bool = False,
    dry_run: bool = False,
    limit: int = None,
    skip_summarize: bool = False,
    skip_strapi: bool = False,
    use_trends: bool = False,
    global_only: bool = False,
):
    """
    Run the full scrape → summarize → push pipeline.

    Args:
        game_slug: Single game to process.
        all_games: Process all configured games.
        dry_run: Skip Strapi push.
        limit: Override article limit per source.
        skip_summarize: Skip AI summarization step.
        skip_strapi: Skip Strapi push step.
        use_trends: Run Google Trends pulse to get dynamic scraping priorities.
        global_only: Only scrape global sources, skip per-game configs.
    """
    start_time = time.time()

    logger.info("=" * 70)
    logger.info("OUTPLAY NEWS SCRAPER PIPELINE")
    logger.info(f"Started at: {datetime.utcnow().isoformat()}Z")
    if use_trends:
        logger.info("Mode: TRENDS-DRIVEN")
    if global_only:
        logger.info("Mode: GLOBAL SOURCES ONLY")
    logger.info("=" * 70)

    all_stats = {
        "games": 0, "scraped": 0, "stored": 0, "summarized": 0,
        "pushed": 0, "global_scraped": 0, "global_tagged": 0,
    }

    # ── Stage 0: Google Trends pulse (optional) ──
    trends_priorities = {}
    if use_trends:
        # Collect game display names for trends lookup
        all_configs = load_all_games()
        game_names = [get_game_display_name(c) for c in all_configs]
        trends_priorities = run_trends_pulse(game_names)

    # ── Stage 1: Global sources ──
    global_stats = scrape_global_sources()
    all_stats["global_scraped"] += global_stats["stored"]
    all_stats["global_tagged"] += global_stats.get("tagged", 0)
    all_stats["scraped"] += global_stats["scraped"]
    all_stats["stored"] += global_stats["stored"]

    if global_only:
        # Only summarize + push, no per-game scraping
        if not skip_summarize:
            sum_stats = summarize_unsummarized()
            all_stats["summarized"] += sum_stats["success"]

        if not skip_strapi:
            push_stats = push_to_strapi(
                limit=limit or Config.MAX_ARTICLES_PER_GAME * 3,
                dry_run=dry_run,
            )
            all_stats["pushed"] += push_stats["pushed"]

    else:
        # ── Stage 2: Per-game scraping ──
        if all_games:
            configs = load_all_games()
        elif game_slug:
            config = load_game_config(game_slug)
            configs = [config] if config else []
        else:
            logger.error("Specify --game <slug>, --all, or --global-only")
            return

        if not configs:
            logger.error("No game configurations found")
            return

        logger.info(f"Processing {len(configs)} game(s): "
                     f"{', '.join(c.get('_slug', '?') for c in configs)}")

        for config in configs:
            slug = config.get("_slug", "unknown")
            display_name = get_game_display_name(config)
            all_stats["games"] += 1

            # Apply trends-driven limit override if available
            effective_limit = limit
            if trends_priorities and display_name in trends_priorities:
                tp = trends_priorities[display_name]
                if not effective_limit:
                    effective_limit = tp.get("limit", Config.MAX_ARTICLES_PER_GAME)
                logger.info(f"  Trends override for {display_name}: "
                             f"limit={effective_limit} ({tp['priority']})")

            # Stage 2a: Scrape per-game sources
            scrape_stats = scrape_game(config)
            all_stats["scraped"] += scrape_stats["scraped"]
            all_stats["stored"] += scrape_stats["stored"]

            # Stage 2b: Summarize
            if not skip_summarize:
                sum_stats = summarize_unsummarized(slug)
                all_stats["summarized"] += sum_stats["success"]

            # Stage 2c: Push to Strapi
            if not skip_strapi:
                push_stats = push_to_strapi(
                    slug,
                    limit=effective_limit or Config.MAX_ARTICLES_PER_GAME,
                    dry_run=dry_run,
                )
                all_stats["pushed"] += push_stats["pushed"]

    elapsed = time.time() - start_time

    logger.info("")
    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Games processed: {all_stats['games']}")
    logger.info(f"Global articles: {all_stats['global_scraped']} stored, "
                f"{all_stats['global_tagged']} auto-tagged")
    logger.info(f"Total articles scraped: {all_stats['scraped']}")
    logger.info(f"New articles stored: {all_stats['stored']}")
    logger.info(f"Articles summarized: {all_stats['summarized']}")
    logger.info(f"Articles pushed to Strapi: {all_stats['pushed']}")
    logger.info(f"Total articles in DB: {get_article_count(Config.DATABASE_PATH)}")
    logger.info(f"Elapsed time: {elapsed:.1f}s")
    logger.info("=" * 70)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Outplay News Scraper Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/orchestrator.py --game cod-mobile           # Scrape + summarize + push for CoD Mobile
  python src/orchestrator.py --all                       # Process all games
  python src/orchestrator.py --all --trends              # All games with Trends-driven priorities
  python src/orchestrator.py --global-only               # Only scrape global news sources
  python src/orchestrator.py --game cod-mobile --dry-run # Scrape + summarize, no Strapi push
  python src/orchestrator.py --expire                    # Archive expired articles
  python src/orchestrator.py --cleanup --days 30         # Delete old drafts
  python src/orchestrator.py --game cod-mobile --scrape-only  # Just scrape, no AI or Strapi
        """,
    )

    parser.add_argument("--game", type=str, help="Game slug to process (e.g., cod-mobile)")
    parser.add_argument("--all", action="store_true", help="Process all configured games")
    parser.add_argument("--trends", action="store_true", help="Use Google Trends to set dynamic scraping priorities")
    parser.add_argument("--global-only", action="store_true", help="Only scrape global news sources (no per-game)")
    parser.add_argument("--dry-run", action="store_true", help="Skip Strapi push")
    parser.add_argument("--limit", type=int, help="Max articles per source")
    parser.add_argument("--scrape-only", action="store_true", help="Only scrape, skip summarize and Strapi")
    parser.add_argument("--no-strapi", action="store_true", help="Skip Strapi push")
    parser.add_argument("--expire", action="store_true", help="Archive expired Strapi articles")
    parser.add_argument("--cleanup", action="store_true", help="Delete old Strapi drafts")
    parser.add_argument("--days", type=int, default=30, help="Days threshold for cleanup (default 30)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Add file logging
    Config.ensure_directories()
    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(file_handler)

    # Handle maintenance commands
    if args.expire:
        stats = expire_articles()
        logger.info(f"Archived {stats['archived']} expired articles")
        return

    if args.cleanup:
        stats = cleanup_drafts(args.days)
        logger.info(f"Deleted {stats['deleted']} old drafts")
        return

    # Validate game selection
    if not args.game and not args.all and not args.global_only:
        parser.error("Specify --game <slug>, --all, or --global-only")

    # Run pipeline
    run_pipeline(
        game_slug=args.game,
        all_games=args.all,
        dry_run=args.dry_run,
        limit=args.limit,
        skip_summarize=args.scrape_only,
        skip_strapi=args.scrape_only or args.no_strapi,
        use_trends=args.trends,
        global_only=args.global_only,
    )


if __name__ == "__main__":
    main()
