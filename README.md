# SwipePads News Scraper

Automated mobile gaming news scraper for Pocket Gamer. Collects articles, generates AI-powered scannable summaries, and exports data for integration into SwipePads mobile games launcher.

---

## Project Status

**Current Phase**: Phase 6 - AI Summarization
**Progress**: 40/89 milestones completed (44.9%)
**Status**: Core pipeline functional, AI integration in progress

### ✅ Completed Phases
- **Phase 0**: Environment & Project Setup ✅
- **Phase 1**: Single Article Scraper ✅
- **Phase 2**: Image Download Pipeline ✅
- **Phase 3**: SQLite Storage ✅
- **Phase 4**: Integration - Single Article Pipeline ✅
- **Phase 5**: Batch Scraping ✅
- **Phase 6**: AI Summarization (1/7 milestones - API client ready)

### 📋 Tracking Files
- **[PROGRESS.md](PROGRESS.md)** - Detailed progress tracker with completion notes
- **[CURRENT_MILESTONE.md](CURRENT_MILESTONE.md)** - Current milestone: M6.2
- **[DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)** - Complete 89-milestone plan

---

## Quick Start

### Prerequisites
- Python 3.11+
- Anthropic API key (for AI summarization)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd swipepads-scraper
```

2. **Set up virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

4. **Initialize database**
```bash
python -c "from src.database import init_db; init_db()"
```

### Usage

**Scrape a single article:**
```bash
python src/pipeline.py --url "https://www.pocketgamer.com/news/article-url"
```

**Batch scrape multiple articles:**
```bash
python src/pipeline.py --batch --limit 20
```

**Force re-scrape existing articles:**
```bash
python src/pipeline.py --batch --limit 10 --force
```

**Verify pipeline integrity:**
```bash
python src/verify_pipeline.py
```

### Testing AI Summarization

**Test API connection:**
```bash
python -m src.summarizer
```

**Generate summary for an article:**
```python
from src.summarizer import summarize_article
summary = summarize_article("Article Title", "Article content text...")
print(summary)
```

---

## Features

### ✅ Implemented
- ✅ Web scraping from Pocket Gamer news listings
- ✅ Article content extraction (title, date, author, content, images)
- ✅ Multi-strategy parsing (JSON-LD → Open Graph → Twitter → HTML)
- ✅ Image download with PIL validation
- ✅ SQLite database storage with upsert (duplicate prevention)
- ✅ Batch processing with rate limiting (2 sec between requests)
- ✅ Progress reporting and error recovery
- ✅ Failed URL logging for retry
- ✅ Comprehensive verification scripts
- ✅ Anthropic Claude API integration
- ✅ Cost tracking for API usage
- ✅ CLI with flexible arguments

### 🚧 In Progress
- 🚧 AI-powered bullet-point summaries (200-300 chars, 3-5 bullets)
- 🚧 Summary storage in database

### 📅 Planned
- [ ] JSON/XML export for CMS integration
- [ ] Automated scheduling (every 4 hours)
- [ ] 30-day data retention with auto-cleanup
- [ ] Daemon mode with health checks

---

## Project Structure

```
swipepads-scraper/
├── docs/                          # Documentation
│   ├── PROJECT_BRIEF.md           # Requirements specification
│   ├── DEVELOPMENT_PLAN.md        # Complete 89-milestone plan
│   └── phases/                    # Phase status files
├── src/                           # Source code
│   ├── config.py                  # Configuration & environment variables
│   ├── scraper.py                 # Web scraping (fetch pages, parse links)
│   ├── parser.py                  # Article parsing (metadata, content, images)
│   ├── image_downloader.py        # Image download & validation
│   ├── database.py                # SQLite operations (CRUD, queries)
│   ├── summarizer.py              # AI summarization (Anthropic Claude)
│   ├── pipeline.py                # Main pipeline orchestration
│   └── verify_pipeline.py         # Verification & integrity checks
├── tests/                         # Test scripts
│   └── test_database.py           # Database unit tests (pytest)
├── data/                          # Database & temp files (git-ignored)
│   └── articles.db                # SQLite database
├── images/                        # Downloaded images (git-ignored)
│   └── YYYY-MM-DD/                # Images organized by date
├── logs/                          # Log files (git-ignored)
│   ├── scraper.log                # Main log file
│   └── failed_urls.txt            # Failed scraping attempts
├── .env                           # Environment variables (git-ignored)
├── .env.example                   # Example environment file
├── .gitignore                     # Git ignore rules
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── PROGRESS.md                    # Progress tracker
└── CURRENT_MILESTONE.md           # Current work pointer
```

---

## Technology Stack

- **Language**: Python 3.12
- **Web Scraping**: requests + BeautifulSoup4 + lxml
- **Database**: SQLite with row factory for dict-like access
- **Image Processing**: Pillow (PIL) for validation
- **AI**: Anthropic Claude 3.5 Sonnet (via anthropic==0.72.0)
- **Configuration**: python-dotenv
- **Testing**: pytest
- **Scheduling**: APScheduler (planned)

---

## Database Schema

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    date TEXT,
    author TEXT,
    content TEXT,
    image_path TEXT,
    summary TEXT,                          -- AI-generated summary
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_url ON articles(url);
CREATE INDEX idx_scraped_at ON articles(scraped_at);
```

---

## Development Approach

This project follows an incremental, milestone-based development approach:

- **10 Phases** covering setup through production deployment
- **89 Granular Milestones** (15-45 minutes each)
- **Verification at each step** - prove features work before moving on
- **Git commits per milestone** - easy rollback and handoff
- **Parallel development** - independent modules built simultaneously

### Development Workflow

**Before starting work:**
1. Check `CURRENT_MILESTONE.md` for what's next
2. Read milestone details in `docs/DEVELOPMENT_PLAN.md`
3. Run verification commands to ensure previous work intact

**After completing work:**
1. Update `PROGRESS.md` with completed milestones
2. Update `CURRENT_MILESTONE.md` to point to next milestone
3. Commit: `git commit -m "Phase X: Milestone Y - Description"`
4. Tag phases: `git tag phase-X-complete`

---

## API Cost Tracking

The summarizer module tracks API usage automatically:

```python
from src.summarizer import cost_tracker

# After generating summaries
print(cost_tracker)
# Output: API Usage: 3 requests, 1800 input tokens, 300 output tokens, $0.0099 total

# Get detailed cost breakdown
stats = cost_tracker.get_cost_estimate()
print(f"Total cost: ${stats['total_cost']:.4f}")
```

**Estimated Costs (Claude 3.5 Sonnet):**
- Per article: ~$0.0035 (~600 input + 100 output tokens)
- 20 articles: ~$0.07
- 100 articles: ~$0.35

---

## Success Criteria

The MVP will be considered complete when:

1. ✅ Scrapes 20+ articles per day automatically
2. 🚧 All articles have 3-5 bullet point summaries (200-300 chars)
3. ✅ Images downloaded and verified on disk
4. [ ] Exports valid JSON/XML files
5. [ ] Runs every 4 hours without intervention
6. ✅ No duplicate articles in database (upsert by URL)
7. [ ] Auto-cleanup of articles older than 30 days

**Current Status**: 5/7 criteria implemented or in progress

---

## Testing

**Run database tests:**
```bash
pytest tests/test_database.py -v
```

**Verify pipeline integrity:**
```bash
python src/verify_pipeline.py
```

**Test scraper:**
```bash
python -c "from src.scraper import fetch_page, parse_article_links; \
           html = fetch_page('https://www.pocketgamer.com/news/'); \
           links = parse_article_links(html, limit=5); \
           print(f'Found {len(links)} articles')"
```

**Test parser:**
```bash
python -c "from src.parser import extract_full_article; \
           from src.scraper import fetch_page; \
           html = fetch_page('https://www.pocketgamer.com/news/...'); \
           article = extract_full_article(html, '...'); \
           print(f'Extracted: {article[\"title\"]}')"
```

---

## Troubleshooting

### Common Issues

**1. Module import errors**
- Ensure virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

**2. Database locked**
- Close any SQLite browser connections
- Check for zombie Python processes: `ps aux | grep python`

**3. API authentication errors**
- Verify `ANTHROPIC_API_KEY` in `.env` file
- Check account has credits: https://console.anthropic.com/settings/billing
- Test connection: `python -m src.summarizer`

**4. Image download failures**
- Check internet connection
- Verify `images/` directory has write permissions
- Review failed URLs: `cat logs/failed_urls.txt`

**5. Scraping errors (401, 403)**
- User agent may be blocked - update in `.env`
- Rate limiting - increase `SCRAPER_RATE_LIMIT_SECONDS`

---

## Configuration

All configuration is managed via `.env` file:

```bash
# AI API Key
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# Scraper Settings
SCRAPER_USER_AGENT=SwipePadsScraper/1.0
SCRAPER_RATE_LIMIT_SECONDS=2

# Database
DATABASE_PATH=data/articles.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/scraper.log

# Retention
ARTICLE_RETENTION_DAYS=30
```

---

## Git Workflow

**Branch naming:** `sculptor/<descriptor>`
**Current branch:** `sculptor/smooth-elite-clam`

**Commit format:**
```
Phase X: Milestone Y - Description

Detailed changes:
- Item 1
- Item 2

Progress: XX/89 milestones (XX.X%)
```

**Tags:**
- `phase-0-complete` through `phase-5-complete` ✅
- Phase 6 in progress

---

## Contributing

This is a solo/small team MVP project. Follow the development plan in order.

**When continuing work:**
1. Read `CURRENT_MILESTONE.md` - shows M6.2 (Summarization Prompt Engineering)
2. Check `PROGRESS.md` - shows 40/89 (44.9%) complete
3. Review git status and recent commits
4. Continue from current milestone

**All commits include:**
```
Co-Authored-By: Claude <noreply@anthropic.com>
Co-authored-by: Sculptor <sculptor@imbue.com>
```

---

## License

Proprietary - SwipePads Commercial Project

---

## Contact

For questions about this project, refer to:
- Project requirements: `docs/PROJECT_BRIEF.md`
- Development plan: `docs/DEVELOPMENT_PLAN.md`
- Progress tracker: `PROGRESS.md`

---

**Last Updated**: 2025-11-03
**Version**: 0.5.0 (Phases 0-5 Complete, Phase 6 In Progress)
**Next Milestone**: M6.2 - Summarization Prompt Engineering
