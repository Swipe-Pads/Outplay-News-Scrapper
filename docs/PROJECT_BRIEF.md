# SwipePads News Scraper - Project Brief

## Executive Summary

Build an automated news collection system that scrapes mobile gaming articles from Pocket Gamer, processes them into scannable news tiles, and exports data for integration into SwipePads - a commercial mobile games launcher for gamers.

---

## Project Context

**Product**: SwipePads (mobile games launcher)
**Component**: External news scraper (feeds data into product, not part of core app)
**Commercial Status**: Commercial product
**Target Audience**: Mobile gamers
**Language**: English only
**Development Approach**: MVP with guerilla methods - use existing solutions, avoid enterprise complexity

---

## Business Problem

SwipePads needs fresh, scannable gaming news displayed in-app to keep users engaged. News must be:

- **Always available**: Minimum 20 news topics rotated daily
- **Mobile-optimized**: Quick to read, "at-a-glance" format
- **Automated**: Requires minimal manual intervention
- **Current**: Updated throughout the day

Manual curation is not scalable. An automated scraper is needed.

---

## Content Scope

### News Source (MVP)

- **Primary**: https://www.pocketgamer.com/news/
- Single source for initial version
- Direct web scraping (no APIs, RSS, or social media)

### Gaming Categories

- **Primary**: FPS (First Person Shooters)
- **Secondary**: MOBA, Battle Royale, Emulators
- Focus on mobile platforms (iOS, Android)

### Visual Reference

**Target Style**: Scannable, bullet-point summaries like news cards - not long-form articles.

Example format:
```
• Valorant Mobile launches today with optimized touch controls
• Cross-progression allows shared unlocks between PC and mobile
• New agent "Pulse" designed exclusively for mobile
• Runs at 60-120fps on devices up to 3 years old
• Free battle pass for early adopters
```

---

## Functional Requirements

### Core Capabilities

1. **Web Scraping**
   - Scrape article list from Pocket Gamer news section
   - Extract full article details from individual article pages
   - Respect website policies (rate limiting, robots.txt)
   - Handle network errors gracefully

2. **Content Extraction**
   Must extract from each article:
   - Title
   - Publication date
   - Author (if available)
   - Full article text/content
   - Main cover image URL
   - Article source URL (for attribution)
   - Tags/categories (if available)

3. **Content Transformation**
   - Transform long articles into **scannable 3-5 bullet point summaries**
   - Each bullet: 1-2 sentences maximum
   - Total summary: ~200-300 characters
   - Style: "At-a-glance" format optimized for mobile reading

4. **Image Management**
   - Download cover images from articles
   - Optimize images for mobile display
   - Store images locally with article references
   - **CRITICAL**: Verify images are actually downloaded (see Testing Requirements)

5. **Data Storage**
   - Store articles with all metadata
   - Track article URLs to prevent duplicates
   - Maintain rolling 30-day data window (auto-delete older content)
   - Log scraping activity (articles found, errors, etc.)

6. **Data Export**
   - Export to structured format (JSON or XML) for CMS import
   - Include all article data + local image paths
   - Support manual or automated export
   - Format should be CMS-agnostic (standard structure)

7. **Automation**
   - Run scraper every 4 hours automatically
   - Schedule: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 (or similar)
   - Each run should collect new articles only (skip duplicates)

8. **Duplicate Prevention**
   - Detect previously scraped articles by URL
   - Skip processing for duplicates
   - Ensure idempotent operation (safe to run multiple times)

---

## Testing & Verification Requirements

### Critical Issue to Prevent
**Previous attempts had "empty folders problem"**: System claimed images were downloaded but folders remained empty. This must NOT happen.

### Mandatory Verification Strategy

The solution MUST include:

1. **Built-in Testing**
   - Test each component independently before integration
   - Verify actual file creation (not just "success" messages)
   - Prove data is stored (not just claimed)
   - Test full pipeline end-to-end

2. **Evidence-Based Verification**
   For each component, provide proof it works:
   - **Images**: Show file listing with sizes, verify image validity
   - **Database**: Query and display actual stored data
   - **Exports**: Show export file contents
   - **Summaries**: Display generated summaries

3. **Verification Commands**
   Include simple verification commands that can be run manually:
   - List downloaded files
   - Query database for article count
   - Display sample article data
   - Check export file contents

4. **Incremental Development**
   Build and verify in stages:
   1. Scraping → verify articles extracted
   2. Images → verify files downloaded
   3. Summarization → verify summaries generated
   4. Storage → verify data persisted
   5. Export → verify files created
   6. Integration → verify full pipeline

**Do NOT claim completion without providing evidence that files exist and data is stored.**

---

## Data Structure Requirements

### Article Object (minimum fields)
```
- id: unique identifier
- url: source article URL (for duplicate detection)
- title: article headline
- summary: 3-5 bullet points (generated)
- content: full article text (raw)
- coverImage: path to downloaded image file
- publishDate: when article was published
- author: article author
- source: "Pocket Gamer"
- sourceUrl: original article URL
- tags: relevant categories/tags
- scrapedAt: timestamp of scraping
```

### Export Format (example structure)
```json
{
  "data": [
    {
      "title": "...",
      "summary": "• point 1\n• point 2\n• point 3",
      "content": "full text...",
      "coverImage": "path/to/image.jpg",
      "publishedAt": "ISO-8601 timestamp",
      "author": "...",
      "source": "Pocket Gamer",
      "sourceUrl": "https://...",
      "tags": ["fps", "mobile"]
    }
  ],
  "meta": {
    "exportedAt": "ISO-8601 timestamp",
    "totalArticles": 25
  }
}
```

---

## Success Criteria

### Minimum Viable Product Success

Project is successful when:

1. **Volume**: Scrapes 20+ articles per day consistently
2. **Quality**: Summaries are scannable and mobile-friendly
3. **Reliability**: Runs automatically every 4 hours without failures
4. **Verification**: All files/data provably exist on disk
5. **Export**: Generates valid export files ready for CMS import
6. **Duplicates**: No duplicate articles in database
7. **Retention**: Auto-cleanup of articles older than 30 days works

### Acceptance Test

Run the scraper. After 24 hours:

- ✅ 100+ articles in database (from 6 runs × 15-20 articles each)
- ✅ 100+ images downloaded and verified on disk
- ✅ All articles have 3-5 bullet point summaries
- ✅ Export file contains all articles in proper format
- ✅ No duplicates in database
- ✅ System running automatically without intervention

---

## Non-Requirements (Out of Scope for MVP)

- ❌ Multiple news sources (only Pocket Gamer for now)
- ❌ Advanced filtering (by game, platform, etc.)
- ❌ Content moderation/quality scoring
- ❌ User interface for browsing articles
- ❌ Direct CMS integration (only export files)
- ❌ Multi-language support
- ❌ Social media integration
- ❌ Analytics/tracking
- ❌ Legal compliance features (GDPR, licensing) - address later
- ❌ Performance optimization beyond basic needs
- ❌ Enterprise features (high availability, clustering, etc.)

---

## Technical Constraints & Preferences

### Philosophy

- **MVP First**: Get it working quickly, iterate later
- **Guerilla Methods**: Use existing tools/libraries, don't reinvent
- **Simple Over Complex**: Avoid enterprise patterns, keep it straightforward
- **Prove It Works**: Testing and verification built into development

### Constraints

- **Budget**: No specific constraints but prefer open-source/free solutions
- **Infrastructure**: Runs on local PC initially
- **Integration**: Must export data files (JSON/XML) - no direct API integration required
- **Maintenance**: Should run with minimal supervision
- **AI**: Use commercial APIs (Claude/OpenAI) for summarization

### What to Avoid

- Complex enterprise frameworks
- Custom solutions where libraries exist
- Over-engineering for scale/performance
- Features not needed for MVP

---

## Deliverables

1. **Working Scraper System**
   - Automated scraping every 4 hours
   - Content processing and summarization
   - Image downloading and optimization
   - Data storage with 30-day retention

2. **Export Mechanism**
   - Generate CMS-ready export files
   - Standard format (JSON or XML)

3. **Verification Tools**
   - Scripts/commands to verify system works
   - Proof that files exist and data is stored

4. **Documentation**
   - Setup instructions
   - How to run scraper
   - How to verify it works
   - How to export data
   - How to troubleshoot common issues

5. **Testing Evidence**
   - Test results showing each component works
   - Proof of file downloads (directory listings)
   - Database queries showing stored articles
   - Sample export file

---

## Technology Decisions

**Selected Stack:**
- **Language**: Python 3.11+
- **Web Scraping**: BeautifulSoup4 + requests
- **Database**: SQLite (zero-config, perfect for MVP)
- **Image Processing**: Pillow
- **Scheduling**: APScheduler
- **AI Summarization**: Anthropic Claude or OpenAI API
- **Environment**: Local PC (Windows/Mac/Linux)
