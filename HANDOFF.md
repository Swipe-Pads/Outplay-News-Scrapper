# Project Handoff - SwipePads News Scraper

**Date**: 2026-03-24
**Status**: v2.0 Complete — Multi-Source System
**Progress**: 89/89 milestones + multi-source extension

---

## Current State

All 10 phases complete + multi-source extension beyond original MVP scope.

### What's working:
- **7 website sources**: Pocket Gamer, GamingOnPhone, DroidGamers, TouchArcade, PocketTactics, AddictingGames, MiniReview
- **14 YouTube channels** via Data API v3
- **3 Reddit subreddits** via public JSON listings (no API credentials)
- **AI summarization** via Anthropic Claude API
- **JSON/XML export** with validation
- **SQLite storage** with 30-day retention + auto-cleanup
- **APScheduler** for automated runs (scrapes all sources, not just Pocket Gamer)
- **Image downloading** with retry logic and PIL validation

### Architecture:
```
src/
├── config.py           # Config from .env
├── scraper.py          # HTTP fetcher + Pocket Gamer link parser
├── parser.py           # HTML article parser (JSON-LD + OG + fallback)
├── image_downloader.py # Image download, validation, retry
├── database.py         # SQLite CRUD, upsert, migration
├── summarizer.py       # Claude API summarization + cost tracking
├── exporter.py         # JSON/XML export (data key, sourceUrl field)
├── pipeline.py         # Orchestrator: multi-source + legacy single-source
├── scheduler.py        # APScheduler daemon (scrape_all_sources)
├── cleanup.py          # Retention cleanup + orphan image deletion
└── sources/
    ├── base.py         # BaseCollector + CollectedItem
    ├── registry.py     # Source registry (lazy load)
    ├── website.py      # 7 website configs + WebsiteCollector
    ├── youtube.py      # 14 channels + YouTubeCollector
    └── reddit.py       # 3 subreddits + RedditCollector
```

---

## How to Resume Work

### 1. Activate Environment
```bash
cd D:/projects/scraper
# Create venv if needed: python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Run Tests
```bash
pytest -v
```

### 3. Run Pipeline
```bash
# Scrape all sources
python -m src.pipeline --all --limit 10

# Scrape specific source type
python -m src.pipeline --source-type website --limit 5

# List registered sources
python -m src.pipeline --list-sources

# Export
python -m src.exporter --format json --validate

# Scheduler (daemon)
python -m src.scheduler --interval 4
```

---

## Configuration

Copy `.env.example` to `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...
YOUTUBE_API_KEY=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

---

## Known Issues / Future Work

- No robots.txt compliance (rate limiting exists but no robots.txt parsing)
- No image optimization (download + validate only, no resize/compress)
- Cost tracker in summarizer is global — accumulates across scheduler runs

---

**Last Updated**: 2026-03-24
