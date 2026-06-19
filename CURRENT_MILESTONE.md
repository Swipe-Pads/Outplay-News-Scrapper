# Project Complete — 89/89 Milestones (100%)

All 10 phases complete. The scraper is production-ready.

---

## CLI Quick Reference

```bash
# Scrape articles
python -m src.pipeline --batch --limit 20

# Scrape + AI summarize
python -m src.pipeline --batch --limit 20 --summarize

# Summarize existing unsummarized articles
python -m src.pipeline --summarize-existing

# Single article
python -m src.pipeline --url "https://..." --summarize

# Export to JSON
python -m src.exporter --format json --validate

# Export to XML
python -m src.exporter --format xml

# Export last 7 days
python -m src.exporter --since 7

# Start scheduler (every 4h scrape + export + cleanup)
python -m src.scheduler --daemon

# Stop scheduler
python -m src.scheduler --stop

# Health check
python -m src.scheduler --health

# Cleanup old articles (dry-run)
python -m src.cleanup --dry-run --days 30

# Cleanup for real
python -m src.cleanup --days 30

# System verification
python verify.py --full

# Run tests
python -m pytest tests/ -v
```

## Architecture

```
pocketgamer.com
    |
    v
scraper.py      (fetch HTML, parse article links)
    |
    v
parser.py       (extract metadata, content, image URL — single parse)
    |
    v
image_downloader.py  (download + validate with PIL + retry)
    |
    v
summarizer.py   (Claude API with rate limiting + cost tracking)
    |
    v
database.py     (SQLite with upsert, summary storage)
    |
    +---> exporter.py    (JSON/XML export with validation)
    +---> cleanup.py     (retention policy, orphan cleanup)
    +---> scheduler.py   (APScheduler daemon, 4h cycle)
    +---> pipeline.py    (orchestrator + CLI)
```
