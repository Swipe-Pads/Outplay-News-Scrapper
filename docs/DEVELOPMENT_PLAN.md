# SwipePads News Scraper - Development Plan

**Version**: 1.0
**Created**: 2025-10-21
**Status**: Ready for Implementation

This document contains the complete granular development plan with 89 milestones across 10 phases.

---

## Overview

**Total Phases**: 10
**Total Milestones**: 89
**Estimated Time**: 20-30 hours (spread over multiple sessions)
**Approach**: Incremental development with verification at each step

---

## Phase Structure

Each phase is broken down into granular milestones (15-45 minutes each) with:
- Clear goal
- Specific tasks
- Verification commands
- Acceptance criteria
- Deliverables

After each phase, create `docs/phases/STATUS_PHASE_X.md` documenting results.

---

## Phase 0: Environment & Project Setup

**Goal**: Set up project structure and verify basic operations work
**Estimated Time**: 1-1.5 hours

### M0.1: Project Structure (15 min)
**Goal**: Create directory structure and verify it exists

**Tasks**:
- Create project root: `swipepads-scraper/`
- Create subdirectories: `src/`, `data/`, `images/`, `exports/`, `logs/`, `tests/`
- Create `.gitignore` (exclude: `data/`, `images/`, `.env`, `*.db`)
- Initialize git repo

**Verification**:
```bash
ls -la
tree -L 2  # or dir /s on Windows
git status
```

**Deliverable**: Empty project structure with .gitignore

---

### M0.2: Python Environment (15 min)
**Goal**: Virtual environment with base dependencies

**Tasks**:
- Create `requirements.txt` with:
  ```
  requests==2.31.0
  beautifulsoup4==4.12.2
  Pillow==10.1.0
  anthropic==0.18.0  # or openai==1.12.0
  python-dotenv==1.0.0
  ```
- Create virtual environment: `python -m venv venv`
- Activate and install: `pip install -r requirements.txt`

**Verification**:
```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -c "import requests, bs4, PIL; print('OK')"
```

**Deliverable**: Working virtual environment

---

### M0.3: Configuration Setup (10 min)
**Goal**: Environment variables and config file

**Tasks**:
- Create `.env.example`:
  ```
  ANTHROPIC_API_KEY=your_key_here
  OPENAI_API_KEY=your_key_here
  SCRAPER_USER_AGENT=SwipePadsScraper/1.0
  ```
- Create `.env` (copy from example)
- Create `src/config.py` with config loader
- Test config loading

**Verification**:
```bash
python -c "from src.config import Config; print(Config.USER_AGENT)"
```

**Deliverable**: Configuration system ready

---

### M0.4: Hello World Test (10 min)
**Goal**: Prove we can create files and they persist

**Tasks**:
- Create `src/test_filesystem.py`
- Write script that creates `data/test.txt` with timestamp
- Read it back and verify content matches
- Delete test file

**Verification**:
```bash
python src/test_filesystem.py
ls -lh data/
cat data/test.txt
```

**Deliverable**: Proof filesystem operations work

**Status File**: Create `docs/phases/STATUS_PHASE_0.md` documenting environment setup

---

## Phase 1: Single Article Scraper

**Goal**: Extract complete data from ONE Pocket Gamer article
**Estimated Time**: 3-4 hours

### M1.1: Fetch Homepage HTML (20 min)
**Goal**: Download Pocket Gamer news page

**Tasks**:
- Create `src/scraper.py`
- Implement `fetch_page(url)` function
- Add user agent, timeout, error handling
- Save HTML to `data/homepage.html` for inspection
- Print first 500 characters

**Verification**:
```bash
python -c "from src.scraper import fetch_page; html = fetch_page('https://www.pocketgamer.com/news/'); print(len(html))"
ls -lh data/homepage.html
head -n 20 data/homepage.html
```

**Acceptance Criteria**:
- [ ] HTML file > 50KB
- [ ] Contains "Pocket Gamer" in content
- [ ] No errors in console

---

### M1.2: Parse Article Links (30 min)
**Goal**: Extract first 5 article URLs from listing page

**Tasks**:
- Add BeautifulSoup parsing to `scraper.py`
- Implement `parse_article_links(html)` function
- Inspect page structure (manually open in browser first)
- Extract article URLs (find correct CSS selectors)
- Print list of URLs

**Verification**:
```bash
python -c "from src.scraper import fetch_page, parse_article_links; html = fetch_page('https://www.pocketgamer.com/news/'); links = parse_article_links(html); print('\n'.join(links[:5]))"
```

**Acceptance Criteria**:
- [ ] Outputs 5+ valid URLs
- [ ] URLs start with `https://www.pocketgamer.com/`
- [ ] URLs are unique

**Decision Point**: Document CSS selectors used (they may change)

---

### M1.3: Fetch Single Article Page (20 min)
**Goal**: Download one article's full page

**Tasks**:
- Take first URL from M1.2
- Fetch article page HTML
- Save to `data/article_sample.html`
- Print page title

**Verification**:
```bash
python src/scraper.py --fetch-article "URL_FROM_M1.2"
ls -lh data/article_sample.html
grep -i "<title>" data/article_sample.html
```

**Acceptance Criteria**:
- [ ] HTML file exists
- [ ] Contains article content (manually verify in browser)
- [ ] Title extracted correctly

---

### M1.4: Extract Article Metadata (45 min)
**Goal**: Parse title, date, author from article page

**Tasks**:
- Implement `parse_article_metadata(html)` in `src/parser.py`
- Manually inspect `data/article_sample.html` to find selectors
- Extract: title (h1), date (meta tag or time element), author
- Return as dictionary
- Handle missing fields gracefully (some articles may lack author)

**Verification**:
```bash
python -c "from src.parser import parse_article_metadata; meta = parse_article_metadata(open('data/article_sample.html').read()); import json; print(json.dumps(meta, indent=2))"
```

**Expected Output**:
```json
{
  "title": "Valorant Mobile is Here",
  "date": "2025-10-15T10:30:00",
  "author": "John Smith"
}
```

**Acceptance Criteria**:
- [ ] Title extracted correctly
- [ ] Date in ISO format
- [ ] Author extracted (or null if missing)

---

### M1.5: Extract Article Content (45 min)
**Goal**: Get main article text (paragraphs)

**Tasks**:
- Implement `parse_article_content(html)` in `src/parser.py`
- Find article body container (inspect HTML manually)
- Extract all paragraphs
- Clean up: remove ads, related articles, footer
- Join into single text block
- Print first 200 characters

**Verification**:
```bash
python -c "from src.parser import parse_article_content; content = parse_article_content(open('data/article_sample.html').read()); print(len(content), 'chars'); print(content[:200])"
```

**Acceptance Criteria**:
- [ ] Content is 200+ characters
- [ ] No HTML tags in output
- [ ] Readable text (not gibberish or ads)

---

### M1.6: Extract Image URL (30 min)
**Goal**: Find main cover image URL

**Tasks**:
- Implement `parse_article_image(html)` in `src/parser.py`
- Look for: og:image meta tag, main article image, hero image
- Priority order (try multiple selectors)
- Validate URL is absolute (not relative)
- Print image URL

**Verification**:
```bash
python -c "from src.parser import parse_article_image; img_url = parse_article_image(open('data/article_sample.html').read()); print(img_url)"
# Copy URL and open in browser - verify it's an image
```

**Acceptance Criteria**:
- [ ] Returns valid image URL
- [ ] URL opens in browser showing image
- [ ] Image is relevant to article (not logo/icon)

---

### M1.7: Integrate Full Article Extraction (30 min)
**Goal**: Combine all parsing into single function

**Tasks**:
- Create `src/article_extractor.py`
- Implement `extract_article(url)` that:
  - Fetches page
  - Extracts all fields (meta + content + image)
  - Returns complete article dict
- Add error handling for each step
- Log each step

**Verification**:
```bash
python -c "from src.article_extractor import extract_article; import json; article = extract_article('URL_FROM_M1.2'); print(json.dumps(article, indent=2))" | tee data/article_full.json
```

**Expected Output**:
```json
{
  "url": "https://...",
  "title": "...",
  "date": "...",
  "author": "...",
  "content": "...",
  "image_url": "https://...",
  "scraped_at": "2025-10-15T12:00:00"
}
```

**Acceptance Criteria**:
- [ ] All fields populated
- [ ] Valid JSON
- [ ] Content > 200 chars
- [ ] Image URL valid

**Status File**: Create `docs/phases/STATUS_PHASE_1.md` with sample article JSON

---

## Phase 2: Image Download Pipeline

**Goal**: Download and verify images with proof they exist
**Estimated Time**: 2.5-3 hours

### M2.1: Simple Image Download (30 min)
**Goal**: Download ONE image from URL

**Tasks**:
- Create `src/image_downloader.py`
- Implement `download_image(url, save_path)`
- Use requests with stream=True
- Save to file
- No validation yet (just download)

**Verification**:
```bash
python -c "from src.image_downloader import download_image; download_image('IMAGE_URL_FROM_M1.6', 'data/test_image.jpg')"
ls -lh data/test_image.jpg
file data/test_image.jpg  # Check file type
```

**Acceptance Criteria**:
- [ ] File exists
- [ ] File size > 1KB
- [ ] `file` command confirms it's an image

---

### M2.2: Image Validation (30 min)
**Goal**: Verify downloaded image is valid

**Tasks**:
- Add Pillow image validation
- Implement `validate_image(file_path)` that:
  - Opens with PIL.Image
  - Checks dimensions > 100x100
  - Returns (width, height, format)
- Raise exception if invalid

**Verification**:
```bash
python -c "from src.image_downloader import validate_image; info = validate_image('data/test_image.jpg'); print(info)"
# Expected: (800, 600, 'JPEG')
```

**Acceptance Criteria**:
- [ ] Returns dimensions and format
- [ ] Rejects corrupted files
- [ ] Rejects tiny images (1x1 tracking pixels)

---

### M2.3: Generate Safe Filenames (20 min)
**Goal**: Create unique, safe image filenames

**Tasks**:
- Implement `generate_image_filename(url, article_title)`
- Sanitize title (remove special chars)
- Add timestamp or hash for uniqueness
- Keep original extension
- Example: `valorant_mobile_is_here_20251015_abc123.jpg`

**Verification**:
```bash
python -c "from src.image_downloader import generate_image_filename; name = generate_image_filename('https://example.com/img.jpg', 'Test: Article!'); print(name)"
# Expected: test_article_20251015_xxxxx.jpg
```

**Acceptance Criteria**:
- [ ] No special characters (safe for all filesystems)
- [ ] Unique (includes hash or timestamp)
- [ ] Keeps file extension

---

### M2.4: Image Directory Management (20 min)
**Goal**: Organize images in date-based folders

**Tasks**:
- Create folder structure: `images/YYYY-MM-DD/`
- Implement `get_image_save_path(filename)` that:
  - Creates date folder if not exists
  - Returns full path: `images/2025-10-15/article_name.jpg`
- Test folder creation

**Verification**:
```bash
python -c "from src.image_downloader import get_image_save_path; path = get_image_save_path('test.jpg'); print(path)"
ls -la images/
ls -la images/2025-10-15/
```

**Acceptance Criteria**:
- [ ] Folder created automatically
- [ ] Path includes date
- [ ] Multiple calls create folders for different dates

---

### M2.5: Download with Validation Pipeline (30 min)
**Goal**: Complete download → validate → save pipeline

**Tasks**:
- Create `download_and_validate(url, article_title)` that:
  - Downloads to temp location first
  - Validates image
  - Moves to final location if valid
  - Deletes temp file if invalid
  - Returns final path or raises error

**Verification**:
```bash
python -c "from src.image_downloader import download_and_validate; path = download_and_validate('IMAGE_URL', 'Test Article'); print(f'Saved to: {path}')"
ls -lh images/2025-10-15/
file images/2025-10-15/*.jpg
```

**Acceptance Criteria**:
- [ ] Image saved to correct location
- [ ] File is valid (checked with Pillow)
- [ ] No temp files left behind
- [ ] Returns path we can store in DB

---

### M2.6: Error Handling & Retries (30 min)
**Goal**: Handle network failures gracefully

**Tasks**:
- Add retry logic (max 3 attempts)
- Handle: timeouts, 404s, invalid images
- Log each attempt
- Return None on failure (don't crash)

**Verification**:
```bash
# Test with bad URL
python -c "from src.image_downloader import download_and_validate; result = download_and_validate('https://example.com/nonexistent.jpg', 'Test'); print(result)"
# Expected: None (with logged errors)

# Test with valid URL
python -c "from src.image_downloader import download_and_validate; result = download_and_validate('VALID_IMAGE_URL', 'Test'); print(result)"
# Expected: path
```

**Acceptance Criteria**:
- [ ] Bad URLs return None (don't crash)
- [ ] Good URLs return path
- [ ] Logs show retry attempts
- [ ] Doesn't hang forever (timeout)

---

### M2.7: Batch Image Test (20 min)
**Goal**: Download 5 images to prove reliability

**Tasks**:
- Use 5 different article image URLs
- Download all
- Count successes vs failures
- List all downloaded files with sizes

**Verification**:
```bash
python src/test_batch_images.py
ls -lh images/2025-10-15/
wc -l images/2025-10-15/*  # Count files
du -sh images/  # Total size
```

**Acceptance Criteria**:
- [ ] 4+ of 5 images downloaded successfully
- [ ] All files > 1KB
- [ ] `file` confirms all are valid images
- [ ] Logs show clear success/failure for each

**Status File**: Create `docs/phases/STATUS_PHASE_2.md` with image download test results

---

## Phase 3: SQLite Storage

**Goal**: Reliable database storage with deduplication
**Estimated Time**: 2.5-3 hours

### M3.1: Database Schema Design (20 min)
**Goal**: Design articles table structure

**Tasks**:
- Create `src/schema.sql` with articles table
- Include all required fields from spec
- Add indexes on url and scraped_at
- Add unique constraint on url

**Verification**:
```bash
cat src/schema.sql
# Manually review - does it match requirements?
```

**Deliverable**: Schema file ready for execution

---

### M3.2: Database Initialization (30 min)
**Goal**: Create database and tables

**Tasks**:
- Create `src/database.py`
- Implement `init_database()` that creates `data/articles.db`
- Execute schema.sql
- Add check to not recreate if exists

**Verification**:
```bash
python -c "from src.database import init_database; init_database(); print('DB created')"
ls -lh data/articles.db
sqlite3 data/articles.db ".schema"
```

**Acceptance Criteria**:
- [ ] Database file created
- [ ] Tables exist
- [ ] Running twice doesn't error

---

### M3.3: Insert Single Article (30 min)
**Goal**: Store one article in database

**Tasks**:
- Implement `insert_article(article_dict)` in `src/database.py`
- Convert dict to SQL INSERT
- Handle NULL values
- Return inserted row ID

**Verification**:
```bash
python -c "from src.database import insert_article; article = {...}; row_id = insert_article(article); print(f'Inserted: {row_id}')"
sqlite3 data/articles.db "SELECT * FROM articles;"
```

**Acceptance Criteria**:
- [ ] Article inserted
- [ ] Query returns the article
- [ ] All fields correct

---

### M3.4: Duplicate Prevention (30 min)
**Goal**: Block duplicate URLs

**Tasks**:
- Implement `article_exists(url)`
- Modify `insert_article()` to check first
- Test with same URL twice

**Verification**:
```bash
# Insert same article twice - second should be rejected
```

**Acceptance Criteria**:
- [ ] First insert succeeds
- [ ] Second insert fails/skips
- [ ] `article_exists()` returns True

---

### M3.5: Query Functions (30 min)
**Goal**: Retrieve articles from database

**Tasks**:
- Implement `get_article_by_id(id)`
- Implement `get_all_articles(limit=100)`
- Implement `get_article_count()`
- Return as dictionaries

**Verification**:
```bash
python -c "from src.database import get_all_articles; articles = get_all_articles(); print(len(articles))"
```

**Acceptance Criteria**:
- [ ] Functions return correct data
- [ ] Return format is dict
- [ ] Limits work correctly

---

### M3.6: Update Operations (20 min)
**Goal**: Update article with summary

**Tasks**:
- Implement `update_article_summary(id, summary)`
- Test updating existing article

**Verification**:
```bash
python -c "from src.database import update_article_summary; update_article_summary(1, '• Test')"
sqlite3 data/articles.db "SELECT summary FROM articles WHERE id=1;"
```

**Acceptance Criteria**:
- [ ] Summary updated
- [ ] Other fields unchanged

---

### M3.7: Database Helper Module (20 min)
**Goal**: Context manager for DB connections

**Tasks**:
- Implement `with get_db_connection() as conn:` pattern
- Auto-commit on success
- Auto-rollback on error

**Verification**:
```bash
python -c "from src.database import get_db_connection; with get_db_connection() as conn: print('OK')"
```

**Acceptance Criteria**:
- [ ] Connections managed properly
- [ ] No leaks

**Status File**: Create `docs/phases/STATUS_PHASE_3.md` with sample queries

---

## Phase 4: Integration - Single Article Pipeline

**Goal**: End-to-end pipeline for ONE article
**Estimated Time**: 2-2.5 hours

### M4.1: Pipeline Script Structure (20 min)
**Goal**: Create main pipeline orchestrator

**Tasks**:
- Create `src/pipeline.py`
- Implement `process_single_article(url)` stub
- Add logging setup
- Add CLI argument parsing

**Verification**:
```bash
python src/pipeline.py --help
```

**Deliverable**: Pipeline skeleton

---

### M4.2: Integrate Scraper + Storage (30 min)
**Goal**: Scrape and store (no images yet)

**Tasks**:
- Extract article
- Check if exists
- Insert if new
- Log steps

**Verification**:
```bash
python src/pipeline.py --url "ARTICLE_URL"
sqlite3 data/articles.db "SELECT title FROM articles ORDER BY id DESC LIMIT 1;"
```

**Acceptance Criteria**:
- [ ] Article scraped and stored
- [ ] Duplicates skipped

---

### M4.3: Add Image Download Step (30 min)
**Goal**: Download image during pipeline

**Tasks**:
- Add image download after extraction
- Store path in DB
- Handle failures gracefully

**Verification**:
```bash
python src/pipeline.py --url "ARTICLE_URL"
ls -lh images/2025-10-15/
```

**Acceptance Criteria**:
- [ ] Article saved
- [ ] Image downloaded
- [ ] Path in DB matches file

---

### M4.4: Transaction Handling (30 min)
**Goal**: Atomic operations

**Tasks**:
- Wrap in try/except
- Cleanup on error
- Commit on success

**Verification**: Test with good/bad URLs

**Acceptance Criteria**:
- [ ] Errors don't crash
- [ ] DB stays consistent

---

### M4.5: Detailed Logging (20 min)
**Goal**: Track every step

**Tasks**:
- Add structured logging to file
- Include timestamps

**Verification**:
```bash
cat logs/scraper.log
```

**Acceptance Criteria**:
- [ ] Each step logged
- [ ] Timestamps present

---

### M4.6: End-to-End Test (30 min)
**Goal**: Process 3 articles successfully

**Verification**:
```bash
# Process 3 different articles
python src/pipeline.py --url "URL1"
python src/pipeline.py --url "URL2"
python src/pipeline.py --url "URL3"

sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"
ls -lh images/2025-10-15/
```

**Acceptance Criteria**:
- [ ] 3 articles in DB
- [ ] 3 images downloaded
- [ ] All paths valid

---

### M4.7: Verification Script (20 min)
**Goal**: Automated integrity check

**Tasks**:
- Create `src/verify_pipeline.py`
- Check article count = image count
- Check all paths exist
- Report issues

**Verification**:
```bash
python src/verify_pipeline.py
```

**Expected Output**:
```
✓ Database: 3 articles
✓ Images: 3 files
✓ All paths valid
✓ Pipeline integrity: OK
```

**Status File**: Create `docs/phases/STATUS_PHASE_4.md` with verification results

---

## Phase 5: Batch Scraping

**Goal**: Scale to process multiple articles
**Estimated Time**: 3-3.5 hours

### M5.1: Article List Scraper (30 min)
**Goal**: Get 20 article URLs from listing

**Tasks**:
- Implement `get_article_urls_from_listing(limit=20)`
- Parse news page
- Extract URLs

**Verification**:
```bash
python -c "from src.scraper import get_article_urls_from_listing; urls = get_article_urls_from_listing(20); print(len(urls))"
```

**Acceptance Criteria**:
- [ ] Returns 20 URLs
- [ ] All unique

---

### M5.2: Rate Limiting (20 min)
**Goal**: Prevent overwhelming server

**Tasks**:
- Implement rate limiting (2 sec delay)
- Log wait times

**Verification**: Check timestamps in logs

**Acceptance Criteria**:
- [ ] 2+ seconds between requests

---

### M5.3: Batch Pipeline Function (30 min)
**Goal**: Process multiple articles

**Tasks**:
- Implement `process_batch(urls)`
- Loop through URLs
- Track: success, skipped, failed
- Continue on failures

**Verification**:
```bash
python src/pipeline.py --batch --limit 5
```

**Acceptance Criteria**:
- [ ] Processes all URLs
- [ ] Returns stats
- [ ] Doesn't stop on failure

---

### M5.4: Progress Reporting (20 min)
**Goal**: Show real-time progress

**Tasks**:
- Add progress logs
- Show ETA

**Verification**: Watch console during batch run

**Acceptance Criteria**:
- [ ] Clear progress shown
- [ ] Timing displayed

---

### M5.5: Error Recovery (30 min)
**Goal**: Handle individual failures

**Tasks**:
- Wrap each article in try/except
- Log errors
- Save failed URLs
- Continue processing

**Verification**:
```bash
cat logs/failed_urls.txt
```

**Acceptance Criteria**:
- [ ] Batch completes despite errors
- [ ] Failed URLs logged

---

### M5.6: First Full Batch Test (45 min)
**Goal**: Scrape 20 real articles

**Verification**:
```bash
python src/pipeline.py --batch --limit 20
sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"
ls images/2025-10-15/ | wc -l
python src/verify_pipeline.py
```

**Acceptance Criteria**:
- [ ] 15+ articles scraped
- [ ] Images match count
- [ ] Verification passes

---

### M5.7: Idempotency Test (20 min)
**Goal**: Running twice doesn't duplicate

**Verification**:
```bash
# Run batch twice
python src/pipeline.py --batch --limit 10
FIRST=$(sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;")
python src/pipeline.py --batch --limit 10
SECOND=$(sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;")
echo "First: $FIRST, Second: $SECOND"
# Should be equal
```

**Acceptance Criteria**:
- [ ] Second run shows all skipped
- [ ] Count unchanged

**Status File**: Create `docs/phases/STATUS_PHASE_5.md` with batch results

---

## Phase 6: Summarization with AI

**Goal**: Generate bullet-point summaries using Claude/OpenAI
**Estimated Time**: 3-3.5 hours

### M6.1: AI Client Setup (30 min)
**Goal**: Test API connection

**Tasks**:
- Create `src/summarizer.py`
- Implement `test_api_connection()`
- Send simple test prompt
- Verify API key works

**Verification**:
```bash
python -c "from src.summarizer import test_api_connection; test_api_connection()"
```

**Decision Point**: Claude or OpenAI?

**Acceptance Criteria**:
- [ ] API key works
- [ ] Test response received

---

### M6.2: Summarization Prompt Engineering (30 min)
**Goal**: Design prompt for bullet points

**Tasks**:
- Create prompt template
- Test with sample article
- Iterate until format correct

**Verification**:
```bash
python -c "from src.summarizer import generate_summary; summary = generate_summary('Title', 'Content...'); print(summary)"
```

**Expected Output**:
```
• First key point
• Second important detail
• Third notable information
```

**Acceptance Criteria**:
- [ ] Returns 3-5 bullets
- [ ] Uses • prefix
- [ ] Concise

---

### M6.3: Summarize Single Article (30 min)
**Goal**: Generate summary for one article

**Tasks**:
- Implement `summarize_article(article_id)`
- Fetch from DB
- Send to AI
- Return summary

**Verification**:
```bash
python -c "from src.summarizer import summarize_article; summary = summarize_article(1); print(summary)"
```

**Acceptance Criteria**:
- [ ] Returns summary
- [ ] 200-300 chars
- [ ] Relevant to content

---

### M6.4: Store Summary in DB (20 min)
**Goal**: Save generated summary

**Verification**:
```bash
python -c "from src.summarizer import summarize_and_save; summarize_and_save(1)"
sqlite3 data/articles.db "SELECT summary FROM articles WHERE id=1;"
```

**Acceptance Criteria**:
- [ ] Summary stored
- [ ] Field no longer NULL

---

### M6.5: Batch Summarization (45 min)
**Goal**: Summarize all articles without summaries

**Tasks**:
- Implement `summarize_all_articles()`
- Query NULL summaries
- Loop and summarize
- Handle rate limits

**Verification**:
```bash
python src/summarizer.py --summarize-all
sqlite3 data/articles.db "SELECT COUNT(*) FROM articles WHERE summary IS NULL;"
# Expected: 0
```

**Acceptance Criteria**:
- [ ] All articles have summaries
- [ ] No errors

---

### M6.6: Cost Tracking (20 min)
**Goal**: Estimate API costs

**Tasks**:
- Log tokens used
- Calculate cost
- Show total

**Verification**:
```bash
cat logs/scraper.log | grep "tokens"
```

**Acceptance Criteria**:
- [ ] Token usage logged
- [ ] Cost estimate shown

---

### M6.7: Integrate into Main Pipeline (30 min)
**Goal**: Auto-summarize new articles

**Tasks**:
- Add summarization to pipeline
- Make optional (--skip-summary flag)

**Verification**:
```bash
python src/pipeline.py --url "NEW_URL"
sqlite3 data/articles.db "SELECT summary FROM articles ORDER BY id DESC LIMIT 1;"
```

**Acceptance Criteria**:
- [ ] New articles auto-summarized
- [ ] Pipeline still works

**Status File**: Create `docs/phases/STATUS_PHASE_6.md` with sample summaries

---

## Phase 7: Export Mechanism

**Goal**: Generate CMS-ready export files
**Estimated Time**: 2-2.5 hours

### M7.1: Export Data Structure (20 min)
**Goal**: Define JSON export format

**Tasks**:
- Create `src/exporter.py`
- Define output structure
- Implement formatting helper

**Verification**: Test with single article

**Acceptance Criteria**:
- [ ] All required fields present
- [ ] Format matches spec

---

### M7.2: Export All Articles (30 min)
**Goal**: Generate complete export file

**Tasks**:
- Query all articles
- Format each
- Add metadata
- Write JSON

**Verification**:
```bash
python -c "from src.exporter import export_articles; export_articles('exports/export.json')"
cat exports/export.json | jq '.meta'
```

**Acceptance Criteria**:
- [ ] Export created
- [ ] Valid JSON
- [ ] All articles included

---

### M7.3: Timestamped Exports (15 min)
**Goal**: Unique export files

**Tasks**:
- Auto-generate filename with timestamp

**Verification**:
```bash
python src/exporter.py --export
ls -lht exports/
```

**Acceptance Criteria**:
- [ ] Unique filenames
- [ ] No overwrites

---

### M7.4: Export Filtering (30 min)
**Goal**: Export subsets

**Tasks**:
- Add --since DATE
- Add --limit N

**Verification**:
```bash
python src/exporter.py --export --since 2025-10-15 --limit 10
```

**Acceptance Criteria**:
- [ ] Filtering works
- [ ] Empty results handled

---

### M7.5: Export Validation (20 min)
**Goal**: Verify export integrity

**Tasks**:
- Check all paths exist
- Validate required fields
- Report issues

**Verification**:
```bash
python src/exporter.py --export --validate
```

**Acceptance Criteria**:
- [ ] Catches missing images
- [ ] Catches missing fields

---

### M7.6: XML Export (Optional, 30 min)
**Goal**: Support XML format

**Decision Point**: XML needed? Skip if JSON sufficient.

**Status File**: Create `docs/phases/STATUS_PHASE_7.md` with sample export

---

## Phase 8: Automation & Scheduling

**Goal**: Run automatically every 4 hours
**Estimated Time**: 3-4 hours

### M8.1: Scheduler Setup (30 min)
**Goal**: Install and test APScheduler

**Tasks**:
- Add APScheduler to requirements
- Create `src/scheduler.py`
- Test simple job

**Verification**: Run test job every 10 seconds for 1 minute

**Acceptance Criteria**:
- [ ] Scheduler runs
- [ ] Jobs execute

---

### M8.2: Scraper Job Definition (20 min)
**Goal**: Define scheduled task

**Tasks**:
- Implement `scheduled_scrape_job()`
- Add error handling

**Verification**: Run manually

**Acceptance Criteria**:
- [ ] Job runs
- [ ] Logs output

---

### M8.3: 4-Hour Schedule Configuration (20 min)
**Goal**: Set up recurring job

**Tasks**:
- Configure every 4 hours
- Add to scheduler

**Verification**: Wait for first execution

**Acceptance Criteria**:
- [ ] Job scheduled correctly
- [ ] First execution succeeds

---

### M8.4: Daemon Mode (30 min)
**Goal**: Run in background

**Tasks**:
- Add --daemon flag
- Create PID file
- Test start/stop

**Verification**:
```bash
python src/scheduler.py --daemon
ps aux | grep scheduler
kill $(cat scheduler.pid)
```

**Acceptance Criteria**:
- [ ] Runs in background
- [ ] Can be stopped

---

### M8.5: Export Job (20 min)
**Goal**: Auto-export after scrape

**Tasks**:
- Add export job to scheduler

**Verification**: Check export files created

**Acceptance Criteria**:
- [ ] Export runs after scrape
- [ ] Files created

---

### M8.6: Health Check Endpoint (Optional, 30 min)
**Goal**: Monitor scheduler status

**Decision Point**: Needed? Can skip for MVP.

---

### M8.7: 24-Hour Test Run (Manual, ongoing)
**Goal**: Let it run for a full day

**Verification**:
```bash
# Start scheduler
python src/scheduler.py --daemon

# After 24 hours:
sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"
sqlite3 data/articles.db "SELECT DATE(scraped_at), COUNT(*) FROM articles GROUP BY DATE(scraped_at);"
```

**Acceptance Criteria**:
- [ ] Runs 24 hours without crash
- [ ] 6 scrapes completed
- [ ] 60-120 articles collected
- [ ] 6 export files generated

**Status File**: Create `docs/phases/STATUS_PHASE_8.md` with scheduler results

---

## Phase 9: Cleanup & Maintenance

**Goal**: Auto-delete articles older than 30 days
**Estimated Time**: 2-2.5 hours

### M9.1: Old Article Query (20 min)
**Goal**: Find articles to delete

**Tasks**:
- Implement `get_old_articles(days=30)`
- Test with mock data

**Verification**: Update test data to old date, query it

**Acceptance Criteria**:
- [ ] Returns old articles
- [ ] Includes image paths

---

### M9.2: Delete Article Records (20 min)
**Goal**: Remove DB entries

**Tasks**:
- Implement `delete_articles(article_ids)`
- Return count deleted

**Verification**:
```bash
sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"
```

**Acceptance Criteria**:
- [ ] Articles deleted
- [ ] Count correct

---

### M9.3: Delete Image Files (30 min)
**Goal**: Remove associated images

**Tasks**:
- Implement `delete_images(image_paths)`
- Check exists before delete
- Remove empty folders

**Verification**:
```bash
ls images/OLD_DATE/
# Should be empty or not exist
```

**Acceptance Criteria**:
- [ ] Files deleted
- [ ] Missing files handled
- [ ] Folders cleaned

---

### M9.4: Orphaned Image Cleanup (30 min)
**Goal**: Remove images not in DB

**Tasks**:
- Scan images directory
- Find orphaned files
- Delete safely

**Verification**:
```bash
python -c "from src.cleanup import find_orphaned_images; print(find_orphaned_images())"
```

**Acceptance Criteria**:
- [ ] Finds orphans
- [ ] Deletes safely

---

### M9.5: Cleanup Job Integration (20 min)
**Goal**: Single cleanup command

**Tasks**:
- Implement `run_cleanup(days=30)`
- Add dry-run mode

**Verification**:
```bash
python src/cleanup.py --dry-run
python src/cleanup.py
```

**Acceptance Criteria**:
- [ ] Dry-run shows preview
- [ ] Actual run works

---

### M9.6: Schedule Cleanup Job (20 min)
**Goal**: Run cleanup daily

**Tasks**:
- Add to scheduler
- Schedule once per day

**Verification**: Check scheduler config

**Acceptance Criteria**:
- [ ] Job scheduled
- [ ] Runs daily

---

### M9.7: Cleanup Verification (20 min)
**Goal**: Test cleanup doesn't break anything

**Verification**:
```bash
# Count before/after
python src/cleanup.py --days 30
# Test pipeline still works
python src/pipeline.py --url "NEW_URL"
```

**Acceptance Criteria**:
- [ ] Only old articles deleted
- [ ] Recent preserved
- [ ] Pipeline works

**Status File**: Create `docs/phases/STATUS_PHASE_9.md` with cleanup results

---

## Phase 10: Final Verification & Documentation

**Goal**: Production-ready system with complete docs
**Estimated Time**: 3-4 hours

### M10.1: Comprehensive Verification Script (45 min)
**Goal**: One command to verify everything

**Tasks**:
- Create `verify.py` in root
- Check all components
- Generate detailed report

**Verification**:
```bash
python verify.py --full
```

**Expected Output**:
```
SwipePads Scraper - System Verification
========================================
✓ Database: 47 articles
✓ Images: 47 files (12.3 MB)
✓ All articles have summaries
✓ All paths valid
✓ Exports: 6 files
✓ Scheduler: Running
========================================
Overall Status: ✓ ALL CHECKS PASSED
```

**Acceptance Criteria**:
- [ ] All checks pass
- [ ] Clear output
- [ ] Exit code: 0 on success

---

### M10.2: Setup Documentation (30 min)
**Goal**: README with setup instructions

**Deliverable**: `README.md` with installation, config, first run

---

### M10.3: Usage Documentation (30 min)
**Goal**: How to use each component

**Deliverable**: `USAGE.md` comprehensive guide

---

### M10.4: Troubleshooting Guide (30 min)
**Goal**: Common issues and solutions

**Deliverable**: `TROUBLESHOOTING.md`

---

### M10.5: Code Comments & Docstrings (45 min)
**Goal**: Make code maintainable

**Tasks**:
- Add docstrings to all functions
- Add type hints
- Comment complex logic

**Acceptance Criteria**:
- [ ] All public functions documented
- [ ] Examples provided

---

### M10.6: Test Coverage Documentation (20 min)
**Goal**: Document what has been tested

**Deliverable**: `TESTING.md`

---

### M10.7: Final End-to-End Test (60 min)
**Goal**: Full system test from scratch

**Tasks**:
- Backup and reset
- Re-run setup from README
- Scrape 20 articles
- Run scheduler for 8 hours
- Verify all components

**Acceptance Criteria**:
- [ ] Setup from README works
- [ ] All checks pass
- [ ] System production-ready

---

### M10.8: Handoff Package (30 min)
**Goal**: Everything needed to hand off

**Deliverable**: `HANDOFF.md` with:
- Current status
- What's completed
- Known issues
- Next steps
- Key files
- How to resume

**Final Actions**:
- Git commit: "Project complete - MVP ready"
- Git tag: `v1.0-mvp`

**Status File**: Create `docs/phases/STATUS_FINAL.md` - Project complete

---

## Appendix: Quick Reference

### Critical Commands
```bash
# Verify environment
python verify.py --full

# Run single article
python src/pipeline.py --url "ARTICLE_URL"

# Run batch scrape
python src/pipeline.py --batch --limit 20

# Export data
python src/exporter.py --export

# Start scheduler
python src/scheduler.py --daemon

# Stop scheduler
kill $(cat scheduler.pid)

# Run cleanup
python src/cleanup.py --days 30

# Check database
sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"

# Check images
ls -lh images/$(date +%Y-%m-%d)/
du -sh images/
```

### Handoff Checklist
- [ ] All STATUS_PHASE_X.md files created
- [ ] PROGRESS.md updated
- [ ] Git tags created for each phase
- [ ] Final verification passed
- [ ] HANDOFF.md created

### Decision Points Summary
1. **Phase 0**: Python version (recommend 3.11+)
2. **Phase 6**: Claude vs OpenAI (either works)
3. **Phase 7**: XML export needed? (skip if JSON sufficient)
4. **Phase 8**: Health check endpoint? (skip for MVP)

---

**End of Development Plan**

For progress tracking, see `PROGRESS.md` in project root.
For current work, see `CURRENT_MILESTONE.md` in project root.
