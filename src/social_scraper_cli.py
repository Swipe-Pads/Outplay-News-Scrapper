#!/usr/bin/env python3
"""
CLI tool for social media scraping.
Scrapes Twitter/Facebook posts for configured games.
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.social.twitter_scraper import TwitterScraper
from src.social.database import (
    init_social_db,
    insert_social_post,
    insert_post_media,
    get_social_posts,
    get_post_count
)


def load_game_profiles():
    """Load game profiles from configuration file."""
    config_path = Path(__file__).parent.parent / "config" / "game_profiles.json"

    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        return None

    with open(config_path, 'r') as f:
        config = json.load(f)

    return config


async def scrape_twitter_game(game_name: str, game_config: dict, save_to_db: bool = True):
    """
    Scrape Twitter for a specific game.

    Args:
        game_name: Name of the game
        game_config: Game configuration dictionary
        save_to_db: Whether to save to database
    """
    print(f"\n{'='*60}")
    print(f"Scraping Twitter for: {game_name}")
    print(f"{'='*60}")

    twitter_url = game_config.get('twitter_url')
    fallback_file = game_config.get('fallback_twitter')

    if not twitter_url:
        print("❌ No Twitter URL configured")
        return []

    # Create scraper
    scraper = TwitterScraper(headless=True)

    try:
        # Scrape tweets
        tweets = await scraper.scrape_profile(
            profile_url=twitter_url,
            game_name=game_name,
            fallback_file=fallback_file
        )

        # Save to database if requested
        if save_to_db and tweets:
            print(f"\n💾 Saving {len(tweets)} tweets to database...")
            saved_count = 0

            for tweet in tweets:
                # Extract media before saving (it's not a DB field)
                media_list = tweet.pop('media', [])

                # Insert tweet
                try:
                    post_id = insert_social_post(tweet)
                    if post_id:
                        saved_count += 1

                        # Insert media
                        for idx, media in enumerate(media_list):
                            media_data = {
                                'post_id': tweet['post_id'],
                                'media_type': media['type'],
                                'media_url': media['url'],
                                'youtube_id': media.get('youtube_id'),
                                'media_order': idx
                            }
                            insert_post_media(media_data)

                except Exception as e:
                    print(f"   ⚠️  Error saving tweet {tweet['post_id']}: {e}")

            print(f"✅ Saved {saved_count} tweets to database")

        return tweets

    finally:
        await scraper.close_browser()


async def scrape_all_games(save_to_db: bool = True):
    """Scrape all enabled games."""
    config = load_game_profiles()
    if not config:
        return

    games = config.get('games', {})
    enabled_games = {name: cfg for name, cfg in games.items() if cfg.get('enabled', False)}

    if not enabled_games:
        print("❌ No games enabled in configuration")
        return

    print(f"\n🎮 Scraping {len(enabled_games)} enabled games:")
    for game_name in enabled_games.keys():
        print(f"   - {game_name}")

    all_tweets = []

    for game_name, game_config in enabled_games.items():
        tweets = await scrape_twitter_game(game_name, game_config, save_to_db)
        all_tweets.extend(tweets)

    print(f"\n{'='*60}")
    print(f"✅ Total tweets scraped: {len(all_tweets)}")
    print(f"{'='*60}")

    return all_tweets


def display_stats():
    """Display statistics about scraped social posts."""
    print(f"\n{'='*60}")
    print("Social Media Database Statistics")
    print(f"{'='*60}")

    # Total posts
    total_posts = get_post_count()
    print(f"\n📊 Total Posts: {total_posts}")

    if total_posts > 0:
        # Posts by platform
        twitter_count = get_post_count(platform='twitter')
        print(f"   Twitter: {twitter_count}")

        # Recent posts
        print(f"\n📝 Recent Posts:")
        recent_posts = get_social_posts(limit=5)
        for post in recent_posts:
            print(f"   • [{post['game_name']}] {post['post_type']}: {post['content'][:60]}...")
            print(f"     Likes: {post['likes']}, Retweets: {post['retweets']}, Views: {post['views']}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Social Media Scraper CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all enabled games
  python src/social_scraper_cli.py --all

  # Scrape specific game
  python src/social_scraper_cli.py --game "Delta Force"

  # Display statistics
  python src/social_scraper_cli.py --stats

  # Initialize database
  python src/social_scraper_cli.py --init-db
        """
    )

    parser.add_argument('--all', action='store_true', help='Scrape all enabled games')
    parser.add_argument('--game', type=str, help='Scrape specific game')
    parser.add_argument('--stats', action='store_true', help='Display statistics')
    parser.add_argument('--init-db', action='store_true', help='Initialize database')
    parser.add_argument('--no-save', action='store_true', help='Don\'t save to database (test mode)')

    args = parser.parse_args()

    # Initialize database if requested
    if args.init_db:
        print("🔧 Initializing social media database...")
        init_social_db()
        return

    # Display stats if requested
    if args.stats:
        display_stats()
        return

    # Scrape all games
    if args.all:
        print("🚀 Starting social media scraper...")
        asyncio.run(scrape_all_games(save_to_db=not args.no_save))
        return

    # Scrape specific game
    if args.game:
        config = load_game_profiles()
        if not config:
            sys.exit(1)

        games = config.get('games', {})
        if args.game not in games:
            print(f"❌ Game not found in configuration: {args.game}")
            print(f"   Available games: {', '.join(games.keys())}")
            sys.exit(1)

        game_config = games[args.game]
        print("🚀 Starting social media scraper...")
        asyncio.run(scrape_twitter_game(args.game, game_config, save_to_db=not args.no_save))
        return

    # No arguments provided
    parser.print_help()


if __name__ == '__main__':
    main()
