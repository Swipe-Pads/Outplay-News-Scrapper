# Outplay News Scraper

Multi-source gaming news aggregation pipeline for the Outplay launcher app. Scrapes Reddit, YouTube, and gaming blogs, generates AI summaries via Claude, and pushes article drafts to Strapi Cloud CMS for human review.

---

## Quick Start

```bash
# Install
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your API keys

# Run (single game)
python src/orchestrator.py --game cod-mobile

# Run (all games)
python src/orchestrator.py --all

# Dry run (no Strapi push)
python src/orchestrator.py --game cod-mobile --dry-run
```

---

## How It Works

```
Game Config (YAML) → Orchestrator
                        ├── Reddit API      → SQLite
                        ├── YouTube API     → SQLite
                        └── Web Scraper     → SQLite
                                               ↓
                                         Claude AI (summarize)
                                               ↓
                                         Strapi Cloud (draft)
```

1. **Scrape**: Pull posts from Reddit, YouTube, and web sources per game config
2. **Store**: Deduplicate and save to SQLite with metadata
3. **Summarize**: Claude 3.5 Haiku generates clean title, 150-char summary, rewritten body
4. **Push**: Create draft articles in Strapi Cloud with thumbnails
5. **Expire**: Auto-archive articles older than 7 days

---

## Configuration

### Required API Keys (.env)

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `ANTHROPIC_API_KEY` | AI summarization | [console.anthropic.com](https://console.anthropic.com) |
| `STRAPI_URL` | CMS API endpoint | Your Strapi Cloud project |
| `STRAPI_TOKEN` | CMS authentication | Strapi Settings → API Tokens |

### Optional API Keys

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `REDDIT_CLIENT_ID` | Reddit scraping | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |
| `REDDIT_CLIENT_SECRET` | Reddit scraping | Same as above |
| `YOUTUBE_API_KEY` | YouTube scraping | [Google Cloud Console](https://console.cloud.google.com) |

Sources without configured API keys are gracefully skipped.

---

## CLI Reference

```bash
# Pipeline
python src/orchestrator.py --game cod-mobile           # Single game
python src/orchestrator.py --all                       # All games
python src/orchestrator.py --game cod-mobile --dry-run # No Strapi push
python src/orchestrator.py --game cod-mobile --scrape-only  # Scrape only
python src/orchestrator.py --game cod-mobile --no-strapi    # Scrape + summarize

# Maintenance
python src/orchestrator.py --expire                    # Archive expired articles
python src/orchestrator.py --cleanup --days 30         # Delete old drafts

# Testing individual modules
python -m src.strapi_client                            # Test Strapi connection
python -m src.summarizer                               # Test AI summarization
python -m src.scrapers.reddit_scraper                  # Test Reddit API
python -m src.scrapers.youtube_scraper                 # Test YouTube API
```

---

## Game Configurations

Games are configured via YAML files in `games/`. Each file defines sources with priority levels (P0-P3).

| Game | Slug | Config | Sources |
|------|------|--------|---------|
| Call of Duty: Mobile | `cod-mobile` | Full (pilot) | 7 sources |
| Free Fire | `free-fire` | Stub | 2 sources |
| Brawl Stars | `brawl-stars` | Stub | 2 sources |
| Mobile Legends | `mobile-legends` | Stub | 2 sources |
| PUBG Mobile | `pubg-mobile` | Stub | 2 sources |
| Wild Rift | `wild-rift` | Stub | 2 sources |

---

## Project Structure

```
outplay-scraper/
├── src/
│   ├── orchestrator.py          # Main pipeline
│   ├── summarizer.py            # Claude AI structured summarizer
│   ├── strapi_client.py         # Strapi Cloud API client
│   ├── database.py              # SQLite with auto-migration
│   ├── config.py                # Environment config
│   ├── game_config.py           # YAML config loader
│   └── scrapers/
│       ├── reddit_scraper.py    # Reddit Data API (OAuth2)
│       ├── youtube_scraper.py   # YouTube Data API v3
│       └── web_scraper.py       # Generic blog/news scraper
├── games/                       # Per-game YAML configs
├── .github/workflows/           # GitHub Actions (daily cron)
├── .env.example                 # Environment template
└── requirements.txt             # Python dependencies
```

---

## Strapi Setup

Create an `Article` collection type in Strapi Cloud with these fields:

- `title` (Short text, required)
- `summary` (Long text)
- `body` (Rich text / Blocks)
- `contentType` (Enum: news, video, community)
- `sourceUrl` (Short text, required)
- `sourceName` (Short text)
- `originalAuthor` (Short text)
- `videoUrl` (Short text)
- `thumbnail` (Media, single image)
- `reviewStatus` (Enum: pending, approved, rejected)
- `priority` (Enum: low, normal, high, urgent)
- `scrapedAt` (Datetime)
- `expiresAt` (Datetime)
- `relevanceScore` (Decimal)
- `game` (Relation → Game collection)

All articles are created as **unpublished drafts** for human review.

---

## Scheduling

The included GitHub Actions workflow (`.github/workflows/nightly-scrape.yml`) runs at 06:00 UTC daily. Add your API keys as repository secrets.

Manual trigger is also supported via `workflow_dispatch`.

---

## Cost Estimates

| Service | Cost | Notes |
|---------|------|-------|
| Claude 3.5 Haiku | ~$0.002/article | ~600 input + 200 output tokens |
| Reddit API | Free | 100 req/min |
| YouTube Data API | Free | 10k units/day |
| Strapi Cloud | Per plan | Free tier available |

Estimated monthly: **$5-15** for AI costs at ~100 articles/day.

---

## License

Proprietary — SwipePads / Outplay Commercial Project

**Version**: 1.0.0
**Last Updated**: 2026-03-10
