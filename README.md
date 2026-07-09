# SwipePads News Scraper

Multi-source mobile gaming news aggregator. Scrapes websites, YouTube channels, and Reddit subreddits. Generates AI summaries, exports to JSON/XML, runs on a schedule.

Built for the SwipePads mobile games launcher.

---

## Status: v2.0 — Multi-Source (23 March 2026)

**89/89 original milestones complete + multi-source extension**

---

## What changed today (23 March 2026)

### Fixes & refactors (from code review)
- Proper Python package structure (`pyproject.toml`, `src/__init__.py`, killed all `sys.path.insert` hacks)
- Parser 3x faster — single BeautifulSoup + shared JSON-LD per article instead of 3 separate parses
- Database: parameterized SQL queries, `datetime.now(timezone.utc)`, `init_db()` once per batch
- Summarizer: configurable model via `Config.CLAUDE_MODEL`, rate limiting with exponential backoff, resettable `CostTracker`
- Logging: single `basicConfig` in pipeline, no duplicate setup across modules

### Phase 6 completed (AI Summarization)
- `summarize_article()` with rate limiting + retry on `RateLimitError`
- `summarize_batch()` for bulk processing with cost tracking
- `update_article_summary()` + `get_articles_without_summary()` in database
- Pipeline CLI: `--summarize` and `--summarize-existing` flags

### Phase 7-10 completed
- **Export** (`src/exporter.py`): JSON/XML, timestamped files, `--since`/`--limit` filtering, validation
- **Scheduler** (`src/scheduler.py`): APScheduler daemon, scrape every 4h, auto-export, daily cleanup, health check
- **Cleanup** (`src/cleanup.py`): retention policy, orphan image cleanup, dry-run mode
- **Verification** (`verify.py`): full system health check

### Multi-source extension (NEW)
- `src/sources/` — collector abstraction with `BaseCollector` ABC
- **5 websites**: pocketgamer, gamingonphone, droidgamers, toucharcade (via RSS), pockettactics (addictinggames & minireview removed — dead weight)
- **12 YouTube channels**: iFerg, RiseofMobileGames, CallOfDutyMobile, BobbyPlays, OrangeJuice, Techzamazing, SnapdragonProSeries, etc.
- **3 Reddit subreddits**: r/AndroidGaming, r/MobileGaming, r/iosgaming
- Database migrated: `source_type`, `source_name`, `content_id` columns
- CLI: `--all`, `--source-type`, `--source`, `--list-sources`

### Newsletter
- Scraped 43 articles from live sources
- Built HTML gaming newsletter with images and section summaries
- Sent via Gmail to team (MT, Kamil Warulik, Mateusz Waligorski)

### Tests
- 68 tests passing (database, parser, summarizer, exporter, cleanup, sources)

---

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — add your API keys

# List all 24 sources
python -m src.pipeline --list-sources

# Scrape all website sources
python -m src.pipeline --source-type website --limit 10

# Scrape everything (websites + YouTube + Reddit)
python -m src.pipeline --all --limit 10

# Scrape + AI summarize
python -m src.pipeline --all --limit 10 --summarize

# Single source
python -m src.pipeline --source gamingonphone --limit 5

# Export to JSON
python -m src.exporter --format json --validate

# Start scheduler (auto scrape every 4h)
python -m src.scheduler --daemon

# Cleanup old articles
python -m src.cleanup --dry-run --days 30

# Run tests
python -m pytest tests/ -v

# System health check
python verify.py --full
```

---

## Weekly Digest (scoring → HTML post → Shopify draft)

Player-first weekly digest: articles are scored 0-100 (AI gamer-value + cross-source
clustering + freshness + engagement), the top items become an English HTML blog post
(sections: Play this week / Mark your calendar / Coming soon / What to watch /
Don't get burned), saved to `data/digests/YYYY-MM-DD-digest.html` and optionally
pushed to Shopify as a **draft** article (a human reviews & publishes).

```bash
# Score articles from the last 7 days
python -m src.pipeline --score

# Generate the digest (last N days, default 7)
python -m src.pipeline --digest --since 7

# Push latest digest as a Shopify blog DRAFT
python -m src.pipeline --publish-digest

# Full weekly flow in one shot
python -m src.pipeline --all --summarize --score --digest --publish-digest
```

The scheduler runs the whole flow automatically every **Monday 09:00**
(disable with `--no-digest`). Shopify setup: set `SHOPIFY_STORE_DOMAIN`,
`SHOPIFY_ADMIN_TOKEN` (shpat_, `write_content` scope) and optionally
`SHOPIFY_BLOG_ID` in `.env` — see `.env.example`.

---

## API Keys needed

| Service | Env Variable | How to get | Cost |
|---------|-------------|-----------|------|
| Anthropic (summaries) | `ANTHROPIC_API_KEY` | console.anthropic.com | Pay per token |
| YouTube Data API v3 | `YOUTUBE_API_KEY` | console.cloud.google.com | Free (10k units/day) |
| Reddit API | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | reddit.com/prefs/apps | Free |

Websites work without any API keys.

---

## Architecture

```
24 sources (websites, YouTube, Reddit)
    |
    v
src/sources/          — BaseCollector -> WebsiteCollector, YouTubeCollector, RedditCollector
    |
    v
src/parser.py         — extract metadata, content, images (single parse)
src/image_downloader.py — download + validate with PIL + retry
    |
    v
src/summarizer.py     — Claude API with rate limiting + cost tracking
    |
    v
src/database.py       — SQLite (source_type, source_name, content_id)
    |
    +---> src/exporter.py    — JSON/XML export with validation
    +---> src/cleanup.py     — retention policy, orphan cleanup
    +---> src/scheduler.py   — APScheduler daemon, 4h cycle
    +---> src/pipeline.py    — orchestrator + CLI
```

---

## TODO

### High Priority
- [ ] Fix PocketGamer scraper — 0 URLs discovered, site may have changed structure
- [x] TouchArcade 403 — fixed via RSS feed + browser User-Agent (falls back gracefully)
- [x] Fix PocketTactics selectors — now targets /{topic}/{article-slug} paths only
- [x] Remove AddictingGames — dead weight (game category pages, no news)
- [x] Remove MiniReview.io — dead weight (JS-rendered, 0 URLs)

### YouTube & Reddit (need API keys)
- [ ] Set up YouTube Data API key and test 14 channels
- [ ] Set up Reddit API credentials and test 3 subreddits
- [ ] Add YouTube channel handle -> ID resolution caching

### Newsletter & Email
- [ ] Build automated newsletter generation module (`src/newsletter.py`)
- [ ] HTML email template with proper MIME encoding
- [ ] Schedule weekly newsletter send
- [ ] Add unsubscribe / recipient management

### Content Quality
- [ ] Filter out non-article pages (category pages, about, profiles)
- [ ] Deduplicate similar articles across sources
- [ ] Add article quality scoring (content length, has image, has date)
- [ ] Improve summarizer prompt for YouTube descriptions vs articles

### Phase 2 Sources (later)
- [ ] Twitter/X API ($100/mo) — 5 accounts to monitor
- [ ] Instagram — 3 accounts (needs business API review)
- [ ] TikTok — 3 accounts (needs research API access)

### Infrastructure
- [ ] Add proper logging to file (rotate daily)
- [ ] Docker container for deployment
- [ ] GitHub Actions CI for tests
- [ ] Dashboard / web UI for viewing scraped content
- [ ] Webhook notifications (Slack/Discord) on new content

---

## Project Structure

```
scraper/
├── src/
│   ├── sources/
│   │   ├── base.py            # BaseCollector ABC
│   │   ├── registry.py        # 24 registered sources
│   │   ├── website.py         # 7 website collectors
│   │   ├── youtube.py         # 14 YouTube channels
│   │   └── reddit.py          # 3 subreddits
│   ├── config.py              # Env vars, Config class
│   ├── database.py            # SQLite with source columns
│   ├── scraper.py             # HTTP fetch + link parsing
│   ├── parser.py              # HTML -> article data
│   ├── image_downloader.py    # PIL validation + retry
│   ├── summarizer.py          # Claude API + cost tracking
│   ├── pipeline.py            # Main CLI orchestrator
│   ├── exporter.py            # JSON/XML export
│   ├── scheduler.py           # APScheduler daemon
│   └── cleanup.py             # Retention + orphan cleanup
├── tests/                     # 68 pytest tests
├── verify.py                  # System health check
├── pyproject.toml
├── requirements.txt
└── .env.example
```
