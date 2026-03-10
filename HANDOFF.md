# Project Handoff — Outplay News Scraper

**Date**: 2026-03-10
**Status**: Full pipeline built, ready for API keys + Strapi setup
**Previous state**: Phase 5 complete (44.9%), single-source Pocket Gamer scraper

---

## What Changed

The scraper has been extended from a single-source Pocket Gamer pipeline into a **multi-source, multi-game news aggregation system** that pushes article drafts to Strapi Cloud CMS.

### Before (Oct 2025)
- Scraped Pocket Gamer only
- Stored in SQLite
- AI summarizer built but not connected
- No CMS integration
- 40/89 milestones (44.9%)

### After (Mar 2026)
- Scrapes Reddit, YouTube, and any web/blog source
- Per-game YAML configuration (6 games configured)
- AI summarization via Claude 3.5 Haiku (structured output)
- Strapi Cloud CMS integration (creates drafts, uploads thumbnails)
- Auto-expiration of 7-day-old articles
- GitHub Actions nightly cron workflow
- Full CLI orchestrator with dry-run mode

---

## How to Set Up

### 1. Install Dependencies

```bash
cd outplay-scraper
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual keys:
```

**Required keys:**
- `ANTHROPIC_API_KEY` — for AI summarization
- `STRAPI_URL` — your Strapi Cloud API URL
- `STRAPI_TOKEN` — Strapi API token (full access)

**Optional (per source):**
- `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` — Reddit scraping
- `YOUTUBE_API_KEY` — YouTube scraping

### 3. Create Strapi Article Content Type

In Strapi Cloud admin, create a new collection type `Article` with these fields:

| Field | Type | Notes |
|-------|------|-------|
| title | Short text | Required |
| summary | Long text | ≤150 chars |
| body | Rich text / Blocks | AI-rewritten content |
| contentType | Enumeration | news, video, community |
| sourceUrl | Short text | Required, used for dedup |
| sourceName | Short text | e.g. "Reddit r/CoDMobile" |
| originalAuthor | Short text | |
| videoUrl | Short text | YouTube/Twitch URL |
| thumbnail | Media (single image) | |
| reviewStatus | Enumeration | pending, approved, rejected |
| priority | Enumeration | low, normal, high, urgent |
| scrapedAt | Datetime | |
| expiresAt | Datetime | Auto-set to scrapedAt + 7 days |
| relevanceScore | Decimal | 0.0 - 1.0 |
| game | Relation (many-to-one) | Links to Game collection |

Also ensure the `Game` collection has a `slug` field for lookup.

### 4. Test Connection

```bash
# Test Strapi
python -m src.strapi_client

# Test Reddit (if configured)
python -m src.scrapers.reddit_scraper

# Test YouTube (if configured)
python -m src.scrapers.youtube_scraper

# Test AI summarizer
python -m src.summarizer
```

### 5. Run Pipeline

```bash
# Single game (pilot)
python src/orchestrator.py --game cod-mobile

# Dry run (no Strapi push)
python src/orchestrator.py --game cod-mobile --dry-run

# All games
python src/orchestrator.py --all

# Scrape only (no AI, no Strapi)
python src/orchestrator.py --game cod-mobile --scrape-only

# Maintenance
python src/orchestrator.py --expire          # Archive expired articles
python src/orchestrator.py --cleanup --days 30  # Delete old drafts
```

### 6. Set Up GitHub Actions

Add these secrets to your GitHub repo settings:
- `ANTHROPIC_API_KEY`
- `STRAPI_URL`
- `STRAPI_TOKEN`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `YOUTUBE_API_KEY`

The workflow at `.github/workflows/nightly-scrape.yml` runs daily at 06:00 UTC.

---

## Project Structure

```
outplay-scraper/
├── .github/workflows/
│   └── nightly-scrape.yml          # Daily cron workflow
├── games/                           # Per-game YAML configs
│   ├── cod-mobile.yaml             # Pilot game (7 sources)
│   ├── free-fire.yaml
│   ├── brawl-stars.yaml
│   ├── mobile-legends.yaml
│   ├── pubg-mobile.yaml
│   └── wild-rift.yaml
├── src/
│   ├── config.py                    # Environment config loader
│   ├── database.py                  # SQLite with migration support
│   ├── summarizer.py                # Claude AI structured summarizer
│   ├── strapi_client.py             # Strapi Cloud REST API v4 client
│   ├── game_config.py               # YAML config loader
│   ├── orchestrator.py              # Main pipeline entry point
│   └── scrapers/
│       ├── __init__.py              # ScrapedContent TypedDict
│       ├── reddit_scraper.py        # Reddit Data API (OAuth2)
│       ├── youtube_scraper.py       # YouTube Data API v3
│       └── web_scraper.py           # Generic blog/news scraper
├── data/                            # SQLite DB (git-ignored)
├── images/                          # Downloaded images (git-ignored)
├── logs/                            # Log files (git-ignored)
├── .env.example                     # Environment template
├── requirements.txt                 # Python dependencies
├── PROGRESS.md                      # Progress tracker
└── HANDOFF.md                       # This file
```

---

## Important Notes

1. **All articles are created as DRAFTS** — `publishedAt: null` in Strapi. Human review required before publishing.

2. **Deduplication** happens at two levels:
   - SQLite: `url` column is UNIQUE
   - Strapi: `article_exists()` checks `sourceUrl` before creating

3. **Content expiry**: Articles auto-expire after 7 days. The `--expire` command archives them in Strapi.

4. **Cost tracking**: The summarizer tracks Claude API costs per run. Check logs for cost summaries.

5. **Graceful degradation**: If a scraper source is not configured (e.g. no Reddit API key), the orchestrator skips it and continues with other sources.

6. **Database migration**: The upgraded `database.py` auto-migrates existing SQLite databases by adding new columns via ALTER TABLE.

---

## What's NOT Done (Out of Scope for This Delivery)

- Twitch scraper (config exists, no implementation yet)
- Twitter/X scraper (API access unclear)
- Google Play store scraper
- Unit tests for new modules (existing `tests/test_database.py` still works)
- Cloudinary image CDN integration (thumbnails go directly to Strapi Media Library)
- EC2 deployment scripts (GitHub Actions handles scheduling)

---

**Last Updated**: 2026-03-10
**Next Steps**: Configure `.env`, create Strapi Article content type, run `--game cod-mobile --dry-run`
