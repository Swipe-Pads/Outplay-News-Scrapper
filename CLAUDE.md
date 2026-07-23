# SwipePads News Scraper

## Overview
Multi-source mobile gaming news aggregator with AI summaries, scheduled scraping, and Strapi CMS sync.

## Stack
- Python 3.11+, SQLite (`data/articles.db`)
- BeautifulSoup + lxml (web), google-api-python-client (YouTube), public JSON listings (Reddit, no API creds)
- Anthropic Claude (AI summaries), APScheduler (scheduling)
- Strapi CMS integration (`src/strapi.py`)

## Commands
```bash
python -m src.pipeline          # Run full scrape + summarize pipeline
python -m src.scheduler         # Start scheduled scraper
pytest                          # Run all tests
pytest tests/test_strapi.py     # Strapi integration tests only
```

## Project Structure
```
src/
├── pipeline.py        # Main orchestrator
├── scraper.py         # Web scraping (Pocket Gamer etc.)
├── summarizer.py      # AI summary generation
├── database.py        # SQLite storage
├── exporter.py        # JSON/XML export
├── image_downloader.py
├── scheduler.py       # APScheduler cron
├── strapi.py          # Strapi CMS sync
├── config.py          # Env + constants
└── cleanup.py         # Data retention
tests/                 # pytest suite
data/                  # SQLite DB + exports
```

## Environment Variables
Copy `.env.example` to `.env`. Required:
- `ANTHROPIC_API_KEY` — AI summaries
- `YOUTUBE_API_KEY` — YouTube Data API v3
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` — Reddit API
- `STRAPI_URL`, `STRAPI_API_TOKEN` — CMS sync

## Status (2026-03-24)
**Code: DONE** — `src/strapi.py` (455 lines), tests, scheduler wiring, DB columns, all 89/89 milestones complete + multi-source extension.

**Blocker: Article content type not deployed to production.**
- Strapi prod at `https://cms.outplay.game` (Strapi Cloud) — has `game` content type (7 games), but `/api/articles` returns 404
- Article content type exists locally in `D:/projects/swipe-pads/api/src/src/api/article/` but **untracked in git**
- Strapi repo at `D:/projects/swipe-pads/` has **no git remote** — local only
- Deploy: `npm run deploy` from `D:/projects/swipe-pads/api/src/`

## Next steps (deploy unblock)
1. Commit article content type to git in swipe-pads repo
2. `npm run deploy` z `D:/projects/swipe-pads/api/src/`
3. Strapi Admin (`cms.outplay.game/admin`) → set API token permissions for article (find, findOne, create, update)
4. Test: `python -m src.strapi --health` then `--sync --batch-size 5`
5. Fill missing API keys in scraper `.env`

## Konwencje
- **Język UI:** EN (kontent dla SwipePads launcher, target users: international gamers)
- **AI summaries:** Claude Sonnet via API, structured output, fallback na pełny text gdy API down
- **Retention:** stary content kasowany przez `cleanup.py` po N dniach (config w `.env`)

## Powiązania
- **`D:/projects/swipe-pads/`** — odbiorca (Strapi CMS hosting). Również lokalny katalog z Article content type pending deploy.

## Memory
`project_scraper.md` w `C:\Users\mtgod\.claude\projects\C--Users-mtgod\memory\` — pełen status, deploy unblock plan, dlaczego pipeline jest "code done blocked on infra".
