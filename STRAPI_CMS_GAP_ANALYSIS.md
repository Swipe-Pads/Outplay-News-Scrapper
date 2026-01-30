# Strapi CMS Integration - AS-IS Gap Analysis Report

**Date**: 2026-01-30
**Prepared For**: waligorskim (Outplay/SwipePads)
**Purpose**: Compare existing Outplay-News-Scrapper with SwipePads Strapi CMS requirements

---

## Executive Summary

You have **two separate projects** with **significant overlap but different end goals**:

1. **Outplay-News-Scrapper** (Current) - Pocket Gamer news scraper at 85.4% completion
2. **SwipePads Content Pipeline** (New) - Multi-game content aggregation with Strapi CMS

**Key Finding**: ~60% of your existing scraper infrastructure can be reused, but requires architectural changes to integrate with Strapi Cloud and support multiple games.

**Recommendation**: Complete Outplay-News-Scrapper first (15 minutes to deploy), then fork/adapt it for SwipePads CMS pipeline.

---

## 1. Project Comparison

### 1.1 Side-by-Side Overview

| Aspect | Outplay-News-Scrapper (Current) | SwipePads CMS Pipeline (Brief) |
|--------|--------------------------------|-------------------------------|
| **Purpose** | Scrape Pocket Gamer mobile gaming news | Aggregate content for 6 specific mobile games |
| **Target Games** | All mobile games (general) | 6 specific games: Free Fire, Brawl Stars, CoD Mobile, Mobile Legends, PUBG Mobile, Wild Rift |
| **Sources** | 1 source: Pocket Gamer website | 12+ source types per game: Reddit, YouTube, Twitch, blogs, wikis, Twitter, etc. |
| **Volume** | ~20+ articles/day from 1 source | ~60 articles/day (10 per game × 6 games) |
| **Content Destination** | Export files (JSON/XML) | Strapi Cloud CMS (REST API) |
| **Review Workflow** | None - auto-publish | Human review in Strapi UI before publishing |
| **AI Summarization** | ✅ Claude Sonnet 4 API | ✅ Claude Haiku API |
| **Storage** | ✅ SQLite database | Strapi Cloud (PostgreSQL via API) |
| **Scheduling** | ✅ Every 4 hours (APScheduler) | Daily at 6 AM (GitHub Actions or EC2 cron) |
| **Deployment** | Local/Docker/Railway/Google Cloud | AWS EC2 or GitHub Actions |
| **Image Handling** | ✅ Download + local storage | Upload to Strapi → Cloudinary |
| **Data Retention** | ✅ 30-day cleanup | 7-day auto-archive (unpublish) |
| **Tech Stack** | Python + BeautifulSoup + SQLite | Node.js/TypeScript + Strapi + multiple APIs |
| **Status** | 85.4% complete, production-ready | Not started (planning phase) |

---

## 2. What You Already Have (Assets)

### ✅ 2.1 Reusable Components

| Component | Current Implementation | Reusability | Notes |
|-----------|----------------------|-------------|-------|
| **AI Summarization** | `src/summarizer.py` with Claude Sonnet 4 | ⭐⭐⭐⭐⭐ 100% | Same API, just change prompt. Already optimized. |
| **Cost Tracking** | `src/cost_logger.py` + `src/cost_stats.py` | ⭐⭐⭐⭐⭐ 100% | Directly reusable for Claude API costs |
| **Scheduling Logic** | `src/scheduler.py` with APScheduler | ⭐⭐⭐⭐ 80% | Concept reusable, may switch to GitHub Actions |
| **Export System** | `src/export.py` (JSON/XML) | ⭐⭐⭐ 60% | Need to replace with Strapi API push instead |
| **Database Schema** | `src/database.py` (SQLite) | ⭐⭐⭐ 60% | Strapi replaces this, but schema design patterns useful |
| **Cleanup Logic** | `src/cleanup.py` (30-day retention) | ⭐⭐⭐ 60% | Similar but Strapi uses unpublish instead of delete |
| **Web Scraping** | `src/scraper.py` + `src/parser.py` | ⭐⭐ 40% | HTML parsing reusable, but need new scrapers per source |
| **Image Pipeline** | `src/image_downloader.py` | ⭐⭐⭐⭐ 80% | Download logic same, upload destination changes |
| **Verification System** | `src/verify_system.py` (19 tests) | ⭐⭐⭐ 60% | Testing patterns reusable, tests need adaptation |
| **CLI Tools** | `src/summarize_cli.py`, `src/export_cli.py` | ⭐⭐ 40% | Useful for debugging, need Strapi equivalents |
| **Docker Deployment** | `Dockerfile`, `docker-compose.yml` | ⭐⭐⭐ 60% | Containerization approach reusable |
| **Documentation** | `DEPLOY.md`, deployment guides | ⭐⭐⭐⭐ 80% | Templates and structure highly reusable |

### ✅ 2.2 Proven Workflows

You've already solved these problems:
- ✅ **Duplicate prevention** by URL
- ✅ **Rate limiting** (configurable delay between requests)
- ✅ **Error handling** (continue on failure, log errors)
- ✅ **Cost monitoring** for AI APIs
- ✅ **Automated scheduling** with job configuration
- ✅ **Image validation** (check file exists, not empty)
- ✅ **Batch processing** with progress reporting
- ✅ **Environment configuration** (.env files)
- ✅ **System verification** (health checks before deployment)

---

## 3. What's Missing (Gaps)

### ❌ 3.1 Critical Gaps for Strapi Integration

| Gap | What's Missing | Impact | Effort to Build |
|-----|---------------|--------|-----------------|
| **1. Strapi API Client** | No code to create articles via Strapi REST API | 🔴 CRITICAL | ⭐⭐ Medium (2-4 hours) |
| **2. Multiple Source Scrapers** | Only Pocket Gamer, need 12+ source types | 🔴 CRITICAL | ⭐⭐⭐⭐⭐ Very High (2-3 weeks) |
| **3. Game Configuration System** | No per-game source mappings | 🔴 CRITICAL | ⭐⭐⭐ High (1 week) |
| **4. Content Type Classification** | No distinction between news/video/community | 🟡 HIGH | ⭐⭐ Medium (1-2 days) |
| **5. Review Status Workflow** | No draft/pending/approved states | 🟡 HIGH | ⭐ Low (few hours with Strapi) |
| **6. Strapi Media Upload** | Images stored locally, not uploaded to Strapi | 🟡 HIGH | ⭐⭐ Medium (1 day) |
| **7. Cloudinary Integration** | No cloud media storage | 🟡 MEDIUM | ⭐ Low (Strapi plugin handles it) |
| **8. 7-Day Expiration** | 30-day cleanup, need 7-day unpublish | 🟢 LOW | ⭐ Low (modify cleanup logic) |
| **9. Video URL Handling** | No YouTube/Twitch video metadata extraction | 🟡 HIGH | ⭐⭐ Medium (1-2 days) |
| **10. API Clients** | No Reddit API, YouTube API, Twitch API clients | 🔴 CRITICAL | ⭐⭐⭐⭐ Very High (1-2 weeks) |
| **11. Node.js/TypeScript** | Python codebase, brief recommends TypeScript | 🟡 MEDIUM | ⭐⭐⭐⭐⭐ Very High (rewrite) |
| **12. Strapi Cloud Setup** | No Strapi instance configured | 🔴 CRITICAL | ⭐ Low (1-2 hours guided setup) |

### ❌ 3.2 Architectural Differences

| Current Architecture | Required Architecture | Gap |
|---------------------|----------------------|-----|
| **Single-source scraper** | Multi-source orchestrator with pluggable scrapers | Need orchestration layer |
| **Direct database writes** | API-first (push to Strapi via REST) | Need HTTP client layer |
| **Immediate publication** | Draft → Review → Publish workflow | Need state management |
| **Self-contained system** | Distributed (scraper + CMS + media storage) | Need service integration |
| **Python monolith** | Microservices approach (brief suggests Node.js) | Language/architecture mismatch |
| **Schedule-driven** | Event-driven (scrape → process → queue for review) | Need async workflow |

---

## 4. Data Model Comparison

### 4.1 Article Schema

| Field | Outplay-News-Scrapper | SwipePads CMS Brief | Compatibility |
|-------|----------------------|---------------------|---------------|
| **id** | ✅ SQLite INTEGER | ✅ Strapi auto-generated | ✅ Compatible |
| **url** | ✅ TEXT UNIQUE | ✅ sourceUrl (string, required) | ✅ Compatible (rename) |
| **title** | ✅ TEXT | ✅ title (string, max 100) | ✅ Compatible |
| **date** | ✅ TEXT (publish date) | ✅ sourcePublishedAt (datetime) | ✅ Compatible (rename) |
| **author** | ✅ TEXT | ✅ originalAuthor (string) | ✅ Compatible |
| **content** | ✅ TEXT (full article) | ✅ body (rich text) | ✅ Compatible |
| **summary** | ✅ TEXT (AI-generated) | ✅ summary (max 200 chars) | ✅ Compatible |
| **image_path** | ✅ TEXT (local path) | ✅ thumbnail (media relation) | ⚠️ Different storage model |
| **scraped_at** | ✅ TIMESTAMP | ✅ scrapedAt (datetime) | ✅ Compatible |
| **updated_at** | ✅ TIMESTAMP | ✅ Strapi auto-managed | ✅ Compatible |
| **game** | ❌ Missing | ✅ game (relation to Game entity) | ❌ Need to add |
| **contentType** | ❌ Missing | ✅ Enum: news/video/community/esports | ❌ Need to add |
| **videoUrl** | ❌ Missing | ✅ YouTube/Twitch embed URL | ❌ Need to add |
| **sourceName** | ❌ Missing (always Pocket Gamer) | ✅ Reddit/YouTube/Blog name | ❌ Need to add |
| **reviewStatus** | ❌ Missing (auto-publish) | ✅ Enum: pending/approved/rejected | ❌ Need to add |
| **priority** | ❌ Missing | ✅ Enum: featured/normal/low | ❌ Need to add |
| **expiresAt** | ❌ Missing (uses cleanup job) | ✅ Datetime (7 days) | ❌ Need to add |
| **publishedAt** | ❌ Missing (assumed) | ✅ Strapi Draft & Publish system | ❌ Need to add |

**Compatibility Score**: 60% overlap, 40% new fields required

### 4.2 New Entity: Game

Your current scraper **does not have** a Game entity. The brief requires:

```typescript
interface Game {
  name: string;
  slug: string;
  icon: Media;
  genres: string[];
  androidPackageId: string;  // For auto-detect installed games

  // Content sources (12+ fields)
  officialBlogUrl?: string;
  redditSubreddit?: string;
  youtubeChannelHandle?: string;
  twitchGameCategory?: string;
  // ... 8+ more source fields

  // Social links (6 fields)
  discordInviteUrl?: string;
  // ... 5 more

  // App context
  googlePlayUrl?: string;
  steamAppId?: string;
}
```

**Impact**: This is a **core architectural change**. Your scraper needs to be game-aware.

---

## 5. Technical Stack Comparison

### 5.1 Technology Alignment

| Layer | Current (Outplay) | Required (Brief) | Alignment |
|-------|------------------|------------------|-----------|
| **Language** | Python 3.11+ | Node.js/TypeScript preferred | ❌ Mismatch |
| **Web Framework** | N/A (CLI app) | Express/Fastify (optional) | - |
| **Scraping** | BeautifulSoup + requests | Puppeteer or native APIs | ⚠️ Different approach |
| **Database** | SQLite | Strapi Cloud (PostgreSQL via API) | ❌ Mismatch |
| **ORM** | sqlite3 (Python) | N/A (REST API) | - |
| **AI Provider** | ✅ Anthropic Claude | ✅ Anthropic Claude | ✅ Match |
| **AI Model** | Sonnet 4 | Haiku (cost-optimized) | ⚠️ Different model |
| **Scheduling** | APScheduler (Python) | GitHub Actions / EC2 cron | ⚠️ Different approach |
| **Image Storage** | Local filesystem | Strapi Media Library → Cloudinary | ❌ Mismatch |
| **Deployment** | Docker / Railway / GCP | AWS EC2 or GitHub Actions | ⚠️ Different platforms |
| **Monitoring** | Logs | Discord webhook / SNS | ⚠️ Different approach |

**Stack Compatibility**: 30% aligned, 70% requires changes or rewrites

### 5.2 Brief's Preferred Approach

The Strapi brief **strongly prefers**:
1. **Buy over Build**: Use SaaS (Apify, Firecrawl) instead of custom scrapers
2. **No-code tools**: n8n.io or Make.com for orchestration
3. **Official APIs**: Reddit API, YouTube API over web scraping
4. **TypeScript**: Matches Strapi ecosystem
5. **Managed services**: GitHub Actions over self-hosted scheduling

Your current scraper is **custom-built Python**, which is the **opposite approach**.

---

## 6. Feature-by-Feature Gap Analysis

### 6.1 Content Acquisition

| Feature | Current | Required | Gap | Effort |
|---------|---------|----------|-----|--------|
| Scrape Pocket Gamer | ✅ Complete | ❌ Not needed (wrong source) | N/A | - |
| Scrape game blogs (6 games) | ❌ Missing | ✅ Required (P0 priority) | 🔴 | ⭐⭐⭐⭐ 2 weeks |
| Reddit API integration | ❌ Missing | ✅ Required (P0 priority) | 🔴 | ⭐⭐⭐ 1 week |
| YouTube API integration | ❌ Missing | ✅ Required (P1 priority) | 🔴 | ⭐⭐⭐ 1 week |
| Twitch API integration | ❌ Missing | ✅ Required (P2 priority) | 🟡 | ⭐⭐ 3 days |
| Twitter/X API | ❌ Missing | ✅ Required (P3, deprioritized due to cost) | 🟢 | ⭐ 1-2 days |
| Wiki scraping | ❌ Missing | ✅ Required (P2 priority) | 🟡 | ⭐⭐ 3-5 days |
| Liquipedia scraping | ❌ Missing | ✅ Optional (esports, not in MVP) | 🟢 | - |
| Google Play "What's New" | ❌ Missing | ✅ Required (P3, fallback source) | 🟢 | ⭐ 2 days |

**Summary**: 1 source implemented (wrong one), need 8+ new sources. **~4-6 weeks of work.**

### 6.2 Content Processing

| Feature | Current | Required | Gap | Effort |
|---------|---------|----------|-----|--------|
| HTML to text extraction | ✅ BeautifulSoup | ✅ Need clean markdown | ⚠️ May need Firecrawl | ⭐ 1-2 days |
| AI summarization | ✅ Claude Sonnet 4 | ✅ Claude Haiku | ⚠️ Change model | ⭐ 1 hour |
| Title cleaning | ✅ Basic | ✅ Remove Reddit formatting, clickbait | ⚠️ Enhance | ⭐ Few hours |
| Summary length | ✅ 200-300 chars | ✅ Max 150 chars | ⚠️ Adjust prompt | ⭐ 1 hour |
| Body length | ✅ Full article | ✅ 1-2 paragraphs (100-200 words) | ⚠️ New prompt | ⭐ Few hours |
| Content type classification | ❌ Missing | ✅ news/video/community/esports | 🟡 | ⭐ 1 day |
| Relevance scoring | ❌ Missing | ✅ 0-1 score for ranking/filtering | 🟡 | ⭐ 1-2 days |
| Video metadata extraction | ❌ Missing | ✅ YouTube thumbnail, video ID, duration | 🟡 | ⭐ 1-2 days |
| Source attribution | ✅ URL tracking | ✅ URL + source name + author | ⚠️ Enhance | ⭐ Few hours |

**Summary**: Core summarization exists, needs ~1 week of enhancements.

### 6.3 Data Management

| Feature | Current | Required | Gap | Effort |
|---------|---------|----------|-----|--------|
| Store articles locally | ✅ SQLite | ❌ Push to Strapi Cloud | 🔴 | ⭐⭐ 2-3 days |
| Duplicate detection by URL | ✅ SQLite UNIQUE | ✅ Query Strapi before creating | ⚠️ Change implementation | ⭐ 1 day |
| Associate with games | ❌ Missing | ✅ Relation to Game entity | 🔴 | ⭐ 1-2 days |
| Draft/publish workflow | ❌ Auto-publish | ✅ Create as draft, manual publish | 🟡 | ⭐ 1 day |
| Review status tracking | ❌ Missing | ✅ pending/approved/rejected | 🟡 | ⭐ Few hours (Strapi handles) |
| 30-day retention | ✅ Cleanup job | ❌ Change to 7-day unpublish | ⚠️ | ⭐ Few hours |
| Image storage | ✅ Local files | ✅ Upload to Strapi → Cloudinary | 🟡 | ⭐⭐ 1-2 days |
| Responsive image sizes | ❌ Missing | ✅ Strapi auto-generates | ⚠️ | ⭐ Strapi handles automatically |

**Summary**: Storage layer needs complete overhaul. **~1 week of work.**

### 6.4 Automation & Operations

| Feature | Current | Required | Gap | Effort |
|---------|---------|----------|-----|--------|
| Scheduled scraping | ✅ Every 4 hours | ✅ Daily at 6 AM | ⚠️ Change schedule | ⭐ Configuration change |
| Scheduler technology | APScheduler (Python) | GitHub Actions or EC2 cron | ⚠️ | ⭐⭐ 1-2 days |
| Per-game processing loop | ❌ Missing | ✅ Iterate 6 games | 🟡 | ⭐ 1 day |
| Per-source processing loop | ❌ Single source | ✅ Iterate 12+ sources | 🔴 | ⭐⭐⭐ 1 week |
| Error handling | ✅ Continue on failure | ✅ Log errors, notify on failure | ⚠️ Enhance | ⭐ 1-2 days |
| Monitoring | ✅ Logs only | ✅ Discord webhook or SNS | 🟢 | ⭐ Few hours |
| Cost tracking | ✅ API usage logging | ✅ Same | ✅ | - |
| Manual trigger | ✅ CLI commands | ✅ workflow_dispatch (GitHub) | ⚠️ | ⭐ Few hours |

**Summary**: Scheduling approach changes, need multi-game orchestration. **~1 week of work.**

### 6.5 Deployment & Infrastructure

| Feature | Current | Required | Gap | Effort |
|---------|---------|----------|-----|--------|
| Docker containerization | ✅ Complete | ✅ Optional (can use GitHub Actions) | ✅ | - |
| Local development | ✅ Working | ✅ Same | ✅ | - |
| Railway deployment | ✅ Guide exists | ❌ Not recommended (prefer EC2) | 🟢 | - |
| AWS EC2 deployment | ✅ Guide exists (GCP) | ✅ EC2 t3.micro recommended | ⚠️ | ⭐⭐ 1-2 days setup |
| GitHub Actions | ❌ Missing | ✅ Recommended approach | 🟡 | ⭐⭐ 1-2 days |
| Environment variables | ✅ .env files | ✅ Same + GitHub Secrets | ⚠️ | ⭐ Few hours |
| Strapi Cloud setup | ❌ Missing | ✅ Required | 🔴 | ⭐ 1-2 hours (guided) |
| Cloudinary setup | ❌ Missing | ✅ Required (free tier) | 🟢 | ⭐ 30 min (Strapi plugin) |

**Summary**: Deployment approach changes slightly. **~2-3 days of setup work.**

---

## 7. Volume & Cost Comparison

### 7.1 Processing Volume

| Metric | Current (Outplay) | Required (SwipePads) | Change |
|--------|------------------|---------------------|--------|
| **Articles/day** | 20-40 (Pocket Gamer) | 60 (10 per game × 6) | +50-200% |
| **Sources scraped** | 1 website | 12+ source types × 6 games = 72+ endpoints | +7,100% |
| **API calls/day** | ~5-10 (Claude only) | ~200+ (Reddit + YouTube + Twitch + Claude) | +2,000% |
| **Images processed/day** | 20-40 | 60 | +50-200% |
| **Storage growth/month** | ~180 MB | ~540 MB | +200% |

### 7.2 Cost Comparison

| Component | Current (Outplay) | Required (SwipePads) | Monthly Cost |
|-----------|------------------|---------------------|--------------|
| **Scraper hosting** | Railway ($5) or EC2 ($0-8) | EC2 t3.micro ($0-8) | $0-8 |
| **AI (Claude)** | Sonnet 4 (~$10-20) | Haiku (~$10-30) | $10-30 |
| **CMS** | None (local SQLite) | Strapi Cloud (free or $29) | $0-29 |
| **Media storage** | None (local) | Cloudinary (free tier) | $0 |
| **APIs** | None | Reddit (free) + YouTube (free) + Twitch (free) | $0 |
| **Database** | None (SQLite) | Included in Strapi | $0 |
| **Monitoring** | None | Discord webhook (free) | $0 |
| **Total** | **$15-28/mo** | **$10-67/mo** | - |

**Budget compliance**: SwipePads brief sets $50-100/mo budget. Current estimate is $10-67/mo. ✅ Within budget.

**Option to reduce costs**: Use Strapi free tier ($0), use Claude Haiku ($10-30), self-host on EC2 ($0-8) = **$10-38/mo total**.

---

## 8. Reuse Strategy

### 8.1 What to Keep

✅ **Keep and adapt**:
1. **AI summarization engine** (`src/summarizer.py`) - Change model to Haiku, adjust prompts
2. **Cost tracking system** (`src/cost_logger.py`) - Use as-is
3. **Image download pipeline** (`src/image_downloader.py`) - Change upload destination
4. **Cleanup logic patterns** (`src/cleanup.py`) - Adapt for 7-day unpublish
5. **Error handling patterns** - Continue-on-failure approach
6. **Environment configuration** (.env management) - Same approach
7. **Documentation structure** - Use as templates

✅ **Keep as reference**:
1. **Database schema design** - Inform Strapi content type design
2. **CLI tools** - Patterns for debugging tools
3. **Verification tests** - Testing approach

### 8.2 What to Rewrite

❌ **Rewrite from scratch**:
1. **All scrapers** - Pocket Gamer → Reddit/YouTube/Twitch/Blogs
2. **Storage layer** - SQLite → Strapi API client
3. **Orchestration** - Single-source → Multi-game/multi-source
4. **Scheduling** - APScheduler → GitHub Actions or cron
5. **Game configuration system** - New requirement
6. **Content type classification** - New requirement

❌ **Consider language switch**:
- Brief strongly recommends **TypeScript/Node.js**
- Your current code is **Python**
- **Decision needed**: Rewrite in TypeScript or continue with Python?

**Pros of keeping Python**:
- You have working code (~85% complete)
- Faster initial development
- Python has great scraping libraries

**Pros of switching to TypeScript**:
- Matches Strapi ecosystem
- Brief's recommendation
- Easier Strapi API integration
- Matches front-end developer's skillset

---

## 9. Migration Paths

### Option A: Fork and Adapt (Fastest to MVP)

**Timeline**: 3-4 weeks
**Approach**: Keep Python, adapt existing code

```
Week 1: Strapi Integration
- [ ] Set up Strapi Cloud
- [ ] Create content types (Game, Article)
- [ ] Build Strapi API client in Python
- [ ] Adapt database layer to push to Strapi
- [ ] Test end-to-end with Pocket Gamer (proof of concept)

Week 2: Multi-Game Architecture
- [ ] Create Game configuration system (YAML)
- [ ] Add game-awareness to scraper
- [ ] Seed 6 games in Strapi
- [ ] Add content type classification
- [ ] Test with CoD Mobile (pilot)

Week 3-4: New Source Scrapers
- [ ] Reddit API client
- [ ] YouTube API client
- [ ] Twitch API client (optional)
- [ ] Blog scraper (Firecrawl or custom)
- [ ] Orchestration layer (run all sources per game)

Week 4: Deployment
- [ ] GitHub Actions workflow
- [ ] Environment setup (EC2 or Actions)
- [ ] Monitoring (Discord webhook)
- [ ] Documentation
```

**Effort**: ~80-120 hours
**Risk**: Medium (building on proven foundation)
**Cost**: Minimal (reuse existing code)

### Option B: Rewrite in TypeScript (Aligns with Brief)

**Timeline**: 6-8 weeks
**Approach**: Start fresh in TypeScript, use existing code as reference

```
Week 1-2: Foundation
- [ ] Set up Node.js/TypeScript project
- [ ] Set up Strapi Cloud
- [ ] Build Strapi API client
- [ ] Port AI summarization to TypeScript
- [ ] Port cost tracking

Week 3-4: Source Integrations
- [ ] Reddit API client
- [ ] YouTube API client
- [ ] Twitch API client
- [ ] Blog scraper (Firecrawl recommended)

Week 5-6: Orchestration & Game System
- [ ] Game configuration loader
- [ ] Multi-source orchestrator
- [ ] Image upload pipeline
- [ ] Content type classification

Week 7-8: Deployment & Testing
- [ ] GitHub Actions workflow
- [ ] Testing with all 6 games
- [ ] Documentation
- [ ] Monitoring
```

**Effort**: ~160-240 hours
**Risk**: High (starting from scratch)
**Cost**: Time investment, but cleaner codebase

### Option C: Hybrid (Buy + Reuse)

**Timeline**: 2-3 weeks
**Approach**: Use SaaS tools for scraping, keep Python for orchestration

```
Week 1: SaaS Setup
- [ ] Apify account + configure Actors (Reddit, YouTube, Twitter)
- [ ] Firecrawl account + test blog scraping
- [ ] Set up Strapi Cloud
- [ ] Configure game sources

Week 2: Integration Layer (Python)
- [ ] Apify API client (fetch datasets)
- [ ] Firecrawl API client
- [ ] Port AI summarization engine
- [ ] Strapi API client
- [ ] Orchestration: Apify/Firecrawl → Claude → Strapi

Week 3: Deployment
- [ ] GitHub Actions or EC2 scheduler
- [ ] Testing with all 6 games
- [ ] Monitoring
```

**Effort**: ~60-80 hours
**Risk**: Low (minimal custom code)
**Cost**: $40-60/mo for Apify + Firecrawl (within $50-100 budget)

---

## 10. Recommendations

### 10.1 Immediate Actions (This Week)

1. **✅ Complete Outplay-News-Scrapper deployment** (15 minutes)
   - Deploy to Railway or local Docker
   - Verify it works end-to-end
   - Document for future reference

2. **🎯 Make strategic decision** (Decision needed from you):
   - **Option A**: Fork Python code, adapt for Strapi (fastest MVP, 3-4 weeks)
   - **Option B**: Rewrite in TypeScript (cleanest, aligns with brief, 6-8 weeks)
   - **Option C**: Use SaaS tools (lowest maintenance, recurring cost, 2-3 weeks)

3. **📋 Set up Strapi Cloud** (1-2 hours)
   - Create account
   - Create Game and Article content types
   - Seed 1 game (CoD Mobile) for pilot
   - Test manual article creation

### 10.2 Phased Rollout (Recommended)

**Phase 1: Pilot with CoD Mobile Only** (2 weeks)
- Goal: Prove the pipeline works for 1 game
- Sources: Reddit + YouTube + Official blog
- Volume: 10 drafts/day → 3 published/day
- Success: Admin can review & publish in Strapi

**Phase 2: Expand to 6 Games** (1-2 weeks)
- Add remaining 5 games
- Same 3 sources per game
- Volume: 60 drafts/day → 18 published/day
- Success: All games producing content

**Phase 3: Add Secondary Sources** (2-3 weeks)
- Add Twitch, Twitter, wikis as optional
- Enhance content quality
- Monitor costs and performance

### 10.3 My Recommendation

**For your situation** (new to deployment, want to test quickly):

1. **Today**: Deploy Outplay-News-Scrapper to Railway (Option 2 from DEPLOYMENT_OPTIONS.md)
   - **Time**: 15 minutes
   - **Result**: Working news scraper in production

2. **This week**: Choose **Option C (Hybrid SaaS)** for SwipePads
   - **Why**: Fastest path to working system (2-3 weeks)
   - **Why**: Lowest maintenance (no custom scrapers to debug)
   - **Why**: Within budget ($40-60/mo for scraping)
   - **Why**: You're unfamiliar with deployment - SaaS reduces complexity

3. **Next 2 weeks**: Build pilot with CoD Mobile
   - Use Apify for Reddit + YouTube
   - Use Firecrawl for official blog
   - Reuse your AI summarization code (Python is fine for this)
   - Push to Strapi via API

4. **After pilot succeeds**: Expand to all 6 games

### 10.4 Don't Do This

❌ **Don't** try to retrofit Outplay-News-Scrapper to be the SwipePads scraper
- Too many architectural differences
- Wrong source (Pocket Gamer vs game-specific sources)
- Will create technical debt

❌ **Don't** rewrite everything in TypeScript right now
- Too time-consuming for MVP
- Brief says "secondary priority" - speed matters more
- Can refactor later if needed

❌ **Don't** build all 12+ source scrapers from scratch
- That's 4-6 weeks of work
- SaaS tools (Apify) already have this solved
- Brief explicitly says "prefer buy over build"

---

## 11. Questions for You

Before proceeding, I need your input on:

1. **Strategic choice**: Which migration path do you prefer?
   - [ ] Option A: Fork Python code (3-4 weeks)
   - [ ] Option B: Rewrite in TypeScript (6-8 weeks)
   - [ ] Option C: Hybrid SaaS approach (2-3 weeks) ← **I recommend this**

2. **Budget allocation**: Confirm total budget for SwipePads content pipeline
   - Brief says $50-100/mo total
   - Current Outplay scraper costs $15-28/mo
   - Are these separate budgets or shared?

3. **Timeline**: When do you need SwipePads content pipeline in production?
   - [ ] ASAP (next 2-4 weeks) → Option C
   - [ ] Normal (next 4-8 weeks) → Option A
   - [ ] Can wait (8-12 weeks) → Option B

4. **Deployment comfort**: After I walk you through deploying Outplay-News-Scrapper, will you be comfortable deploying the SwipePads pipeline yourself?
   - This affects whether we optimize for ease of deployment

5. **Front-end dev status**: When does the front-end developer need the Strapi API ready?
   - This affects our timeline

---

## 12. Next Steps

**After you answer the questions above**, I will:

1. **Create detailed implementation plan** for your chosen option
2. **Set up Strapi Cloud** with content types (I can guide you step-by-step)
3. **Build pilot scraper** for CoD Mobile
4. **Integrate with your existing AI summarization code**
5. **Deploy and test end-to-end**

**Estimated time to working pilot**: 2-4 weeks depending on option chosen.

---

## Appendix: File Inventory

### Current Project (Outplay-News-Scrapper)

**Status**: 85.4% complete (76/89 milestones)
**Location**: `/home/user/Outplay-News-Scrapper`

```
Key Files:
- src/summarizer.py (AI engine) ← REUSABLE
- src/cost_logger.py (cost tracking) ← REUSABLE
- src/image_downloader.py (image pipeline) ← REUSABLE
- src/scraper.py (Pocket Gamer scraper) ← REPLACE
- src/database.py (SQLite) ← REPLACE with Strapi
- src/scheduler.py (APScheduler) ← REPLACE with GitHub Actions
- DEPLOY_RAILWAY.md (deployment guide) ← USE AS TEMPLATE
- docker-compose.yml (containerization) ← REUSABLE PATTERN
```

### Strapi Brief (SwipePads Content Pipeline)

**Status**: Not started (planning phase)
**Location**: `/home/user/intro`

```
Key Files:
- CONTENT_PIPELINE_BRIEF.md (1800 lines - COMPLETE SPEC)
- DEVELOPER_HANDOFF.md (implementation guide)
- SCRAPER_COMPARISON.md (tool evaluation)
- Game configs: Need to create (6 YAML files)
- Strapi setup: Not done yet
```

---

**END OF REPORT**

**Action Required**: Please answer the 5 questions in Section 11 so I can proceed with implementation planning.
