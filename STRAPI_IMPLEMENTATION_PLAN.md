# SwipePads Strapi CMS - Implementation Plan

**Date**: 2026-01-30
**Project**: Branch Outplay-News-Scrapper → SwipePads Multi-Game Content Pipeline
**Approach**: Adapt existing Python solution with Strapi Cloud integration
**Estimated Timeline**: 3-4 weeks (60-100 hours)

---

## Executive Summary

**Strategy**: Keep existing Python codebase, add new components for multi-game/multi-source orchestration and Strapi integration.

**Key Principles**:
1. **Reuse what works**: AI summarization, cost tracking, image handling, error patterns
2. **Add new layers**: Game system, source orchestration, Strapi API client
3. **Parallel development**: Independent scrapers can be built simultaneously
4. **Incremental validation**: Test each component before integration
5. **Pilot-first**: Prove with CoD Mobile before expanding to 6 games

**Phases**:
- **Phase 0**: Foundation & Strapi Setup (2-3 days) - Sequential
- **Phase 1**: Core Integration Layer (3-4 days) - Sequential
- **Phase 2**: Source Scrapers (1-2 weeks) - **Parallel**
- **Phase 3**: Orchestration & Game System (3-4 days) - Sequential
- **Phase 4**: Deployment & Testing (2-3 days) - Sequential

---

## Table of Contents

1. [Current State Inventory](#1-current-state-inventory)
2. [Target Architecture](#2-target-architecture)
3. [Phase Breakdown](#3-phase-breakdown)
4. [Parallelization Strategy](#4-parallelization-strategy)
5. [Dependency Map](#5-dependency-map)
6. [Effort Estimates](#6-effort-estimates)
7. [Risk Assessment](#7-risk-assessment)
8. [Acceptance Criteria](#8-acceptance-criteria)

---

## 1. Current State Inventory

### 1.1 What We're Keeping (No Changes)

```python
✅ KEEP AS-IS:
src/cost_logger.py          # Cost tracking - works perfectly
src/cost_stats.py           # Cost display - works perfectly
requirements.txt            # Python dependencies (add new ones)
.env.example               # Environment template (add Strapi vars)
.gitignore                 # Git config
```

### 1.2 What We're Adapting (Modify)

```python
⚙️ ADAPT:
src/summarizer.py          # Change model: Sonnet 4 → Haiku
                          # Adjust prompts for new requirements
                          # Add content type classification

src/image_downloader.py    # Keep download logic
                          # Add: Upload to Strapi instead of local save
                          # Add: Thumbnail fallback logic

src/cleanup.py            # Keep cleanup patterns
                          # Change: 30-day delete → 7-day unpublish
                          # Change: SQLite → Strapi API calls

src/verify_system.py      # Keep testing patterns
                          # Add: Strapi connectivity tests
                          # Add: Game config validation
```

### 1.3 What We're Replacing (Rewrite)

```python
🔄 REPLACE:
src/scraper.py            → src/sources/pocket_gamer.py (archive)
                          → src/sources/reddit_source.py (new)
                          → src/sources/youtube_source.py (new)
                          → src/sources/blog_source.py (new)

src/parser.py             → Incorporated into source-specific scrapers

src/database.py           → src/strapi_client.py (new)
                          # SQLite → Strapi REST API

src/pipeline.py           → src/orchestrator.py (new)
                          # Single article → Multi-game orchestration

src/scheduler.py          → .github/workflows/scrape.yml (new)
                          # APScheduler → GitHub Actions
```

### 1.4 What We're Adding (New)

```python
🆕 NEW COMPONENTS:
src/game_config.py        # Load game configs from YAML
src/strapi_client.py      # Strapi REST API client
src/orchestrator.py       # Multi-game/multi-source coordinator
src/sources/              # Source-specific scrapers
  ├── reddit_source.py    # Reddit API integration
  ├── youtube_source.py   # YouTube Data API v3
  ├── twitch_source.py    # Twitch API (optional)
  ├── blog_source.py      # Generic blog scraper
  └── base_source.py      # Abstract base class

games/                    # Game configuration files
  ├── cod-mobile.yaml
  ├── free-fire.yaml
  ├── brawl-stars.yaml
  ├── mobile-legends.yaml
  ├── pubg-mobile.yaml
  └── wild-rift.yaml

.github/workflows/
  └── scrape.yml          # GitHub Actions scheduler

tests/
  └── test_strapi_client.py
  └── test_game_config.py
  └── test_sources.py
```

---

## 2. Target Architecture

### 2.1 High-Level Flow

```
┌────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                            │
│  (src/orchestrator.py - NEW)                               │
│                                                            │
│  for each game in games/:                                  │
│    1. Load game config (YAML)                              │
│    2. Run source scrapers → ScrapedContent[]               │
│    3. Deduplicate against Strapi                           │
│    4. AI summarize → ProcessedArticle[]                    │
│    5. Push to Strapi as drafts                             │
│    6. Upload thumbnails                                    │
│    7. Log results                                          │
└────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐        ┌──────────┐        ┌──────────┐
   │ Reddit   │        │ YouTube  │        │  Blog    │
   │ Source   │        │ Source   │        │ Source   │
   └──────────┘        └──────────┘        └──────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  AI Summarizer  │
                     │  (ADAPTED)      │
                     └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │ Strapi Client   │
                     │  (NEW)          │
                     └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  Strapi Cloud   │
                     │  (External)     │
                     └─────────────────┘
```

### 2.2 Data Flow

```python
# Input: Game configuration
game = load_game_config("games/cod-mobile.yaml")
# → {name: "CoD Mobile", sources: {reddit: {...}, youtube: {...}}}

# Step 1: Scrape from sources
scraped_content = []
for source_type, config in game.sources.items():
    scraper = get_source_scraper(source_type)
    results = scraper.scrape(config)
    scraped_content.extend(results)
# → [ScrapedContent{title, body, url, source, imageUrl, ...}, ...]

# Step 2: Deduplicate
existing_urls = strapi_client.get_article_urls(days=7)
new_content = [c for c in scraped_content if c.url not in existing_urls]

# Step 3: AI Processing
processed = []
for content in new_content:
    summary = summarizer.summarize(content)
    content_type = classify_content_type(content)
    relevance = score_relevance(content, game)
    processed.append(ProcessedArticle(...))
# → [ProcessedArticle{title, summary, body, contentType, ...}, ...]

# Step 4: Push to Strapi
for article in processed[:10]:  # Top 10 per game
    draft = strapi_client.create_draft_article(article, game.id)
    if article.imageUrl:
        strapi_client.upload_thumbnail(draft.id, article.imageUrl)
# → Articles in Strapi with reviewStatus="pending"
```

---

## 3. Phase Breakdown

### Phase 0: Foundation & Strapi Setup

**Duration**: 2-3 days (16-20 hours)
**Dependencies**: None (start immediately)
**Parallelizable**: No - foundational work

#### Milestones

**M0.1: Strapi Cloud Setup** (2-3 hours)
```markdown
Tasks:
- [ ] Create Strapi Cloud account
- [ ] Create new project: "swipepads-content"
- [ ] Note API URL and generate API token
- [ ] Configure Cloudinary upload provider
- [ ] Enable responsive image generation

Deliverables:
- Strapi Cloud instance running
- API credentials documented in .env.strapi.example

Acceptance:
- Can access Strapi admin UI
- API returns 200 on health check
```

**M0.2: Strapi Content Types** (3-4 hours)
```markdown
Tasks:
- [ ] Create "Game" collection type
  Fields:
    - name (string, required)
    - slug (uid, based on name)
    - icon (media)
    - genres (JSON)
    - androidPackageId (string)
    - officialBlogUrl (string)
    - redditSubreddit (string)
    - youtubeChannelHandle (string)
    - youtubeChannelId (string)
    - ... (all source fields from brief)

- [ ] Create "Article" collection type
  Fields:
    - title (string, max 100)
    - summary (text, max 200)
    - body (rich text)
    - thumbnail (media)
    - videoUrl (string)
    - contentType (enum: news/video/community)
    - sourceUrl (string, required)
    - sourceName (string)
    - originalAuthor (string)
    - reviewStatus (enum: pending/approved/rejected)
    - scrapedAt (datetime)
    - expiresAt (datetime)
    - priority (enum: featured/normal/low)
    - game (relation: many-to-one with Game)

- [ ] Enable Draft & Publish on Article
- [ ] Configure list view filters

Deliverables:
- Screenshot of content type schemas
- API endpoints documented

Acceptance:
- GET /api/games returns empty array
- GET /api/articles returns empty array
- Can create Article manually in admin UI
```

**M0.3: Seed Test Game** (1 hour)
```markdown
Tasks:
- [ ] Upload CoD Mobile icon to Media Library
- [ ] Create CoD Mobile game entry
  - name: "Call of Duty: Mobile"
  - slug: "cod-mobile"
  - redditSubreddit: "CoDMCompetitive"
  - youtubeChannelHandle: "@PlayCODMobile"
  - youtubeChannelId: "UCwxBp4sgbUY6RsDg32cAAbw"
  - ... (populate known sources)

- [ ] Create 2-3 test articles manually
  - Test draft creation
  - Test publishing
  - Test filtering by game

Deliverables:
- 1 game in Strapi
- 3 test articles (1 draft, 2 published)

Acceptance:
- GET /api/games?populate=icon returns CoD Mobile
- GET /api/articles?filters[publishedAt][$notNull]=true returns 2 articles
- GET /api/articles?filters[game][slug]=cod-mobile works
```

**M0.4: Project Structure Reorganization** (2 hours)
```markdown
Tasks:
- [ ] Create new directory structure:
  src/sources/
  games/
  tests/

- [ ] Move existing files:
  src/scraper.py → archive/pocket_gamer_scraper.py
  src/parser.py → archive/pocket_gamer_parser.py

- [ ] Create placeholder files:
  src/strapi_client.py (stub)
  src/game_config.py (stub)
  src/orchestrator.py (stub)
  src/sources/base_source.py (stub)

- [ ] Update requirements.txt:
  + praw (Reddit API)
  + google-api-python-client (YouTube)
  + python-twitch-client (Twitch, optional)
  + PyYAML (game configs)

Deliverables:
- New project structure
- Updated requirements.txt
- README updated with new architecture

Acceptance:
- pip install -r requirements.txt succeeds
- All existing tests still pass
```

**M0.5: Environment Configuration** (1 hour)
```markdown
Tasks:
- [ ] Create .env.strapi.example:
  STRAPI_URL=https://your-project.api.strapi.io
  STRAPI_TOKEN=your-api-token
  REDDIT_CLIENT_ID=your-reddit-client-id
  REDDIT_CLIENT_SECRET=your-reddit-client-secret
  YOUTUBE_API_KEY=your-youtube-api-key
  ANTHROPIC_API_KEY=your-claude-api-key (existing)

- [ ] Update .gitignore for new structure
- [ ] Create games/.gitkeep
- [ ] Document API credential setup in SETUP.md

Deliverables:
- .env.strapi.example
- Updated .gitignore
- SETUP.md with API credential instructions

Acceptance:
- All required env vars documented
- Clear instructions for obtaining each credential
```

---

### Phase 1: Core Integration Layer

**Duration**: 3-4 days (20-28 hours)
**Dependencies**: Phase 0 complete
**Parallelizable**: Some tasks can overlap

#### Milestones

**M1.1: Strapi API Client** (6-8 hours)
```python
# src/strapi_client.py

Tasks:
- [ ] Implement StrapiClient class
  - __init__(base_url, api_token)
  - create_draft_article(article_data, game_id)
  - get_article_by_source_url(url)
  - get_game_by_slug(slug)
  - upload_thumbnail(article_id, image_url_or_buffer)
  - unpublish_expired_articles(days=7)
  - get_article_urls(days=7)  # For deduplication

- [ ] Error handling:
  - Retry logic (3 attempts with backoff)
  - Handle 401 (bad token)
  - Handle 404 (not found)
  - Handle 429 (rate limit)

- [ ] Response parsing:
  - Extract data from Strapi's nested JSON structure
  - Handle pagination for list queries

- [ ] Logging:
  - Log all API calls
  - Log errors with full response body

Code Structure:
```python
import requests
import logging
from typing import Dict, List, Optional

class StrapiClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        })

    def create_draft_article(self, article: Dict, game_id: int) -> Dict:
        """Create article in Strapi as draft with reviewStatus=pending"""
        payload = {
            "data": {
                "title": article['title'],
                "summary": article['summary'],
                "body": article['body'],
                "contentType": article['contentType'],
                "sourceUrl": article['sourceUrl'],
                "sourceName": article['sourceName'],
                "originalAuthor": article.get('originalAuthor'),
                "videoUrl": article.get('videoUrl'),
                "reviewStatus": "pending",
                "scrapedAt": article['scrapedAt'],
                "expiresAt": article['expiresAt'],
                "priority": article.get('priority', 'normal'),
                "game": {"connect": [{"id": game_id}]},
                # publishedAt NOT set → creates as draft
            }
        }
        response = self._post('/api/articles', json=payload)
        return response.json()

    def upload_thumbnail(self, article_id: int, image_source) -> Dict:
        """Upload image and link to article"""
        # Implementation details...
        pass

    def get_article_urls(self, days: int = 7) -> List[str]:
        """Get all source URLs from recent articles for deduplication"""
        # Implementation details...
        pass

    def _post(self, endpoint: str, **kwargs):
        """POST with retry logic"""
        # Implementation details...
        pass
```

Deliverables:
- src/strapi_client.py (200-300 lines)
- tests/test_strapi_client.py

Acceptance:
- Can create draft article
- Can upload thumbnail
- Can query existing articles
- All error cases handled gracefully
- Unit tests pass (mocked API responses)
```

**M1.2: Game Configuration System** (4-5 hours)
```python
# src/game_config.py

Tasks:
- [ ] Define YAML schema for game configs
- [ ] Implement config loader
- [ ] Validation (required fields, valid URLs)
- [ ] Create template game config

Code Structure:
```python
import yaml
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class SourceConfig:
    type: str  # 'reddit', 'youtube', 'blog', etc.
    enabled: bool
    priority: int  # 0 = highest
    config: Dict  # Type-specific config

@dataclass
class GameConfig:
    id: str
    name: str
    slug: str
    android_package_id: str
    sources: List[SourceConfig]

    @classmethod
    def load(cls, yaml_path: str) -> 'GameConfig':
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data['game'])

    @classmethod
    def load_all(cls, games_dir: str = 'games') -> List['GameConfig']:
        """Load all game configs from directory"""
        configs = []
        for yaml_file in Path(games_dir).glob('*.yaml'):
            configs.append(cls.load(str(yaml_file)))
        return configs

def load_game_config(game_slug: str) -> GameConfig:
    """Load single game config by slug"""
    path = f"games/{game_slug}.yaml"
    return GameConfig.load(path)
```

Game Config Template (games/cod-mobile.yaml):
```yaml
game:
  id: "cod-mobile"
  display_name: "Call of Duty: Mobile"
  slug: "cod-mobile"
  android_package_id: "com.activision.callofduty.shooter"

  sources:
    reddit:
      enabled: true
      priority: 0
      subreddit: "CoDMCompetitive"
      flair_filters: ["News", "Announcement", "Update"]
      sort: "hot"
      limit: 20

    youtube:
      enabled: true
      priority: 1
      channel_handle: "@PlayCODMobile"
      channel_id: "UCwxBp4sgbUY6RsDg32cAAbw"
      search_terms: ["cod mobile update", "cod mobile news"]
      max_age_days: 7
      limit: 10

    blog:
      enabled: true
      priority: 0
      url: "https://www.callofduty.com/blog"
      scrape_method: "html"  # or "rss"
      limit: 10
```

Deliverables:
- src/game_config.py (100-150 lines)
- games/cod-mobile.yaml (template)
- tests/test_game_config.py

Acceptance:
- Can load game config from YAML
- Can load all game configs
- Invalid YAML raises clear error
- Missing required fields detected
```

**M1.3: Adapt AI Summarization** (3-4 hours)
```python
# Modify src/summarizer.py

Tasks:
- [ ] Change model: claude-sonnet-4 → claude-3-5-haiku-20241022
- [ ] Update prompt template:
  - Max 150 chars (was 200-300)
  - Body: 1-2 paragraphs (100-200 words)
  - Add game context to prompt
  - Add content type context

- [ ] Add content type classification:
  - Analyze content to determine: news/video/community

- [ ] Add relevance scoring:
  - Score 0-1 based on game relevance
  - Use for ranking (top 10 per game)

- [ ] Update cost tracking:
  - Haiku has different pricing
  - Ensure cost_logger still works

Code Changes:
```python
# Before
def summarize_article(title: str, content: str) -> str:
    prompt = f"Summarize in 200-300 characters: {title}\n{content}"
    # ... call Claude Sonnet 4

# After
def summarize_article(
    title: str,
    content: str,
    game_name: str,
    content_type: str = 'news'
) -> Dict[str, str]:
    """Returns {summary, body, contentType, relevanceScore}"""

    prompt = f"""Summarize this {content_type} for {game_name} players.

Game: {game_name}
Content Type: {content_type}
Title: {title}

Full Content:
{content[:2000]}

Requirements:
- Summary: 1-2 sentences, max 150 characters
- Body: 1-2 paragraphs, 100-200 words
- Focus on what changed and why players care
- Use active voice, no clickbait

Output as JSON:
{{
  "summary": "...",
  "body": "...",
  "contentType": "news" | "video" | "community",
  "relevanceScore": 0.0-1.0
}}
"""

    response = anthropic.messages.create(
        model='claude-3-5-haiku-20241022',  # Changed
        max_tokens=500,
        messages=[{'role': 'user', 'content': prompt}]
    )

    # Parse JSON response
    result = json.loads(response.content[0].text)
    return result
```

Deliverables:
- Updated src/summarizer.py
- New prompt templates
- Content type classifier
- Relevance scorer
- Updated tests

Acceptance:
- Summaries ≤150 chars
- Body is 1-2 paragraphs
- Content type correctly classified
- Relevance score is 0-1
- Cost tracking works with Haiku
```

**M1.4: Adapt Image Pipeline** (2-3 hours)
```python
# Modify src/image_downloader.py → src/image_uploader.py

Tasks:
- [ ] Keep: Download image from URL
- [ ] Keep: Validate image (size, format)
- [ ] Change: Upload to Strapi instead of local save
- [ ] Add: YouTube thumbnail fallback
  - https://img.youtube.com/vi/{VIDEO_ID}/maxresdefault.jpg
- [ ] Add: Game icon fallback (if no image)

Code Changes:
```python
# Before
def download_image(url: str, save_path: str) -> str:
    # Download and save locally
    return save_path

# After
def download_and_upload_thumbnail(
    article_id: int,
    image_url: Optional[str],
    youtube_video_id: Optional[str],
    strapi_client: StrapiClient
) -> Optional[str]:
    """Download image and upload to Strapi, return uploaded URL"""

    # Determine image source
    if image_url:
        source_url = image_url
    elif youtube_video_id:
        source_url = f"https://img.youtube.com/vi/{youtube_video_id}/maxresdefault.jpg"
    else:
        # No image available, Strapi article created without thumbnail
        # Mobile app will use game icon as fallback
        return None

    # Download
    response = requests.get(source_url, timeout=10)
    if response.status_code != 200:
        return None

    # Validate
    if not is_valid_image(response.content):
        return None

    # Upload to Strapi
    uploaded = strapi_client.upload_thumbnail(article_id, response.content)
    return uploaded['url']
```

Deliverables:
- src/image_uploader.py (renamed from image_downloader.py)
- YouTube thumbnail fallback logic
- Updated tests

Acceptance:
- Can download and upload to Strapi
- YouTube fallback works
- Invalid images handled gracefully
- No local storage (all in Strapi)
```

---

### Phase 2: Source Scrapers (PARALLEL)

**Duration**: 1-2 weeks (30-50 hours total, but parallelizable)
**Dependencies**: Phase 1 complete
**Parallelizable**: YES - Each source can be built independently

#### Strategy

Each source scraper is **completely independent**. They can be:
- Built by different developers
- Built by the same developer in any order
- Built by an AI agent working on multiple files
- Tested independently before integration

**Common Interface** (all scrapers implement this):

```python
# src/sources/base_source.py

from abc import ABC, abstractmethod
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class ScrapedContent:
    """Standardized output from all source scrapers"""
    title: str
    body: str
    source_url: str
    source_name: str
    source_type: str  # 'reddit', 'youtube', 'blog', etc.
    game_slug: str

    # Optional fields
    original_author: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    youtube_video_id: Optional[str] = None
    source_published_at: Optional[str] = None

    # Metadata
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())

class BaseSource(ABC):
    """Abstract base class for all source scrapers"""

    def __init__(self, game_slug: str, config: Dict):
        self.game_slug = game_slug
        self.config = config

    @abstractmethod
    def scrape(self) -> List[ScrapedContent]:
        """Fetch content from source, return standardized format"""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Return display name for this source"""
        pass
```

#### M2.1: Reddit Source Scraper (8-10 hours) - PARALLEL

```python
# src/sources/reddit_source.py

Tasks:
- [ ] Set up PRAW (Python Reddit API Wrapper)
- [ ] Implement RedditSource(BaseSource)
  - Connect to Reddit API
  - Query subreddit with flair filters
  - Parse post into ScrapedContent
  - Handle rate limiting (100 requests/min)
  - Extract images from posts

- [ ] Handle edge cases:
  - Deleted posts
  - Empty/removed content
  - Private subreddits
  - Invalid flair filters

Example:
```python
import praw
from typing import List
from .base_source import BaseSource, ScrapedContent

class RedditSource(BaseSource):
    def __init__(self, game_slug: str, config: Dict):
        super().__init__(game_slug, config)
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent='SwipePads Content Scraper v1.0'
        )

    def scrape(self) -> List[ScrapedContent]:
        subreddit_name = self.config['subreddit']
        flair_filters = self.config.get('flair_filters', [])
        sort_method = self.config.get('sort', 'hot')
        limit = self.config.get('limit', 20)

        subreddit = self.reddit.subreddit(subreddit_name)

        if sort_method == 'hot':
            posts = subreddit.hot(limit=limit)
        elif sort_method == 'new':
            posts = subreddit.new(limit=limit)
        elif sort_method == 'top':
            time_filter = self.config.get('time_filter', 'day')
            posts = subreddit.top(time_filter=time_filter, limit=limit)

        results = []
        for post in posts:
            # Filter by flair
            if flair_filters and post.link_flair_text not in flair_filters:
                continue

            # Extract image
            image_url = None
            if hasattr(post, 'url') and post.url.endswith(('.jpg', '.png', '.gif')):
                image_url = post.url
            elif hasattr(post, 'preview'):
                # Extract from preview
                image_url = post.preview['images'][0]['source']['url']

            content = ScrapedContent(
                title=post.title,
                body=post.selftext or post.url,
                source_url=f"https://reddit.com{post.permalink}",
                source_name=f"Reddit r/{subreddit_name}",
                source_type="reddit",
                game_slug=self.game_slug,
                original_author=f"u/{post.author.name}" if post.author else None,
                image_url=image_url,
                source_published_at=datetime.fromtimestamp(post.created_utc).isoformat()
            )
            results.append(content)

        return results

    def get_source_name(self) -> str:
        return f"Reddit r/{self.config['subreddit']}"
```

Deliverables:
- src/sources/reddit_source.py (150-200 lines)
- tests/test_reddit_source.py (mocked API)
- Documentation: Reddit API setup guide

Acceptance:
- Can fetch 20 posts from r/CoDMCompetitive
- Flair filtering works
- Images extracted
- Rate limiting respected
- Returns List[ScrapedContent]
```

#### M2.2: YouTube Source Scraper (8-10 hours) - PARALLEL

```python
# src/sources/youtube_source.py

Tasks:
- [ ] Set up Google API Python Client
- [ ] Implement YouTubeSource(BaseSource)
  - Query channel for recent videos
  - Extract video metadata
  - Generate thumbnail URL
  - Parse into ScrapedContent

- [ ] Handle:
  - API quota (10k requests/day)
  - Private/deleted videos
  - Live streams vs regular videos

Example:
```python
from googleapiclient.discovery import build
from typing import List
from .base_source import BaseSource, ScrapedContent

class YouTubeSource(BaseSource):
    def __init__(self, game_slug: str, config: Dict):
        super().__init__(game_slug, config)
        self.youtube = build(
            'youtube', 'v3',
            developerKey=os.getenv('YOUTUBE_API_KEY')
        )

    def scrape(self) -> List[ScrapedContent]:
        channel_id = self.config['channel_id']
        max_results = self.config.get('limit', 10)
        max_age_days = self.config.get('max_age_days', 7)

        # Get uploads playlist ID
        channel_response = self.youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get recent videos
        playlist_response = self.youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=max_results
        ).execute()

        results = []
        for item in playlist_response['items']:
            video_id = item['snippet']['resourceId']['videoId']
            published_at = item['snippet']['publishedAt']

            # Check if within max age
            if not self._is_recent(published_at, max_age_days):
                continue

            # Get video details
            video_response = self.youtube.videos().list(
                part='snippet,contentDetails',
                id=video_id
            ).execute()

            video = video_response['items'][0]['snippet']

            content = ScrapedContent(
                title=video['title'],
                body=video['description'],
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                source_name=f"YouTube {self.config.get('channel_handle', 'channel')}",
                source_type="youtube",
                game_slug=self.game_slug,
                video_url=f"https://www.youtube.com/watch?v={video_id}",
                youtube_video_id=video_id,
                image_url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                source_published_at=published_at
            )
            results.append(content)

        return results

    def get_source_name(self) -> str:
        return f"YouTube {self.config.get('channel_handle', 'channel')}"

    def _is_recent(self, published_at: str, max_days: int) -> bool:
        published = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - published
        return age.days <= max_days
```

Deliverables:
- src/sources/youtube_source.py (150-200 lines)
- tests/test_youtube_source.py (mocked API)
- Documentation: YouTube API setup guide

Acceptance:
- Can fetch 10 recent videos from channel
- Video metadata complete
- Thumbnail URLs correct
- Respects max_age_days filter
- Returns List[ScrapedContent]
```

#### M2.3: Blog Source Scraper (6-8 hours) - PARALLEL

```python
# src/sources/blog_source.py

Tasks:
- [ ] Implement BlogSource(BaseSource)
- [ ] Support two modes:
  1. RSS feed parsing
  2. HTML scraping (BeautifulSoup)
- [ ] Extract article metadata
- [ ] Handle pagination

Example:
```python
import feedparser
import requests
from bs4 import BeautifulSoup
from typing import List
from .base_source import BaseSource, ScrapedContent

class BlogSource(BaseSource):
    def scrape(self) -> List[ScrapedContent]:
        method = self.config.get('scrape_method', 'rss')

        if method == 'rss':
            return self._scrape_rss()
        else:
            return self._scrape_html()

    def _scrape_rss(self) -> List[ScrapedContent]:
        feed_url = self.config['url']
        limit = self.config.get('limit', 10)

        feed = feedparser.parse(feed_url)
        results = []

        for entry in feed.entries[:limit]:
            # Extract image from enclosure or content
            image_url = None
            if 'media_content' in entry:
                image_url = entry.media_content[0]['url']
            elif 'enclosures' in entry and entry.enclosures:
                image_url = entry.enclosures[0].href

            content = ScrapedContent(
                title=entry.title,
                body=entry.summary or entry.description,
                source_url=entry.link,
                source_name=feed.feed.title,
                source_type="blog",
                game_slug=self.game_slug,
                image_url=image_url,
                source_published_at=entry.get('published', entry.get('updated'))
            )
            results.append(content)

        return results

    def _scrape_html(self) -> List[ScrapedContent]:
        # Similar to existing Pocket Gamer scraper
        # Use BeautifulSoup to parse article list
        # Extract links, titles, summaries
        pass
```

Deliverables:
- src/sources/blog_source.py (200-250 lines)
- Support for RSS and HTML
- tests/test_blog_source.py

Acceptance:
- Can parse RSS feed
- Can scrape HTML article list
- Extracts images from various formats
- Returns List[ScrapedContent]
```

#### M2.4: Twitch Source Scraper (6-8 hours) - PARALLEL (OPTIONAL)

```python
# src/sources/twitch_source.py

Tasks:
- [ ] Set up Twitch API client
- [ ] Implement TwitchSource(BaseSource)
- [ ] Fetch top clips for game category
- [ ] Extract clip metadata

Note: Optional for MVP. Can be added later.

Deliverables:
- src/sources/twitch_source.py
- tests/test_twitch_source.py

Acceptance:
- Can fetch top clips for "Call of Duty: Mobile" category
- Clip thumbnails extracted
- Returns List[ScrapedContent]
```

#### M2.5: Source Factory (2 hours) - AFTER scrapers done

```python
# src/sources/__init__.py

Tasks:
- [ ] Create factory function to instantiate scrapers
- [ ] Register all source types

Example:
```python
from typing import Dict
from .base_source import BaseSource
from .reddit_source import RedditSource
from .youtube_source import YouTubeSource
from .blog_source import BlogSource
from .twitch_source import TwitchSource

SOURCE_REGISTRY = {
    'reddit': RedditSource,
    'youtube': YouTubeSource,
    'blog': BlogSource,
    'twitch': TwitchSource,
}

def get_source_scraper(
    source_type: str,
    game_slug: str,
    config: Dict
) -> BaseSource:
    """Factory function to create source scraper"""
    scraper_class = SOURCE_REGISTRY.get(source_type)
    if not scraper_class:
        raise ValueError(f"Unknown source type: {source_type}")

    return scraper_class(game_slug, config)
```

Deliverables:
- src/sources/__init__.py
- Source registry

Acceptance:
- Can instantiate any source scraper by type
- Unknown types raise clear error
```

---

### Phase 3: Orchestration & Game System

**Duration**: 3-4 days (20-28 hours)
**Dependencies**: Phase 1 + Phase 2 complete
**Parallelizable**: No - integrates all components

#### M3.1: Multi-Game Orchestrator (10-12 hours)

```python
# src/orchestrator.py

Tasks:
- [ ] Load all game configurations
- [ ] For each game:
  - Run all enabled source scrapers
  - Deduplicate against Strapi
  - AI summarize and classify
  - Rank by relevance
  - Push top 10 to Strapi
  - Upload thumbnails
  - Log results

- [ ] Error handling:
  - Game scrape failure doesn't stop others
  - Source scrape failure doesn't stop game
  - Continue on AI/upload errors

- [ ] Progress reporting:
  - Log per-game stats
  - Overall summary at end

- [ ] Rate limiting:
  - Respect API limits (Reddit, YouTube)
  - Throttle Strapi requests

Example Structure:
```python
class ContentOrchestrator:
    def __init__(self):
        self.strapi = StrapiClient(
            os.getenv('STRAPI_URL'),
            os.getenv('STRAPI_TOKEN')
        )
        self.summarizer = ArticleSummarizer()

    def run_for_all_games(self):
        """Main entry point"""
        games = GameConfig.load_all('games/')
        logging.info(f"Processing {len(games)} games")

        for game in games:
            try:
                self.process_game(game)
            except Exception as e:
                logging.error(f"Game {game.slug} failed: {e}")
                continue

        logging.info("All games processed")

    def process_game(self, game: GameConfig):
        """Process single game"""
        logging.info(f"Processing {game.name}")

        # Step 1: Scrape from all sources
        all_content = []
        for source_config in game.sources:
            if not source_config.enabled:
                continue

            try:
                scraper = get_source_scraper(
                    source_config.type,
                    game.slug,
                    source_config.config
                )
                content = scraper.scrape()
                all_content.extend(content)
                logging.info(f"  {source_config.type}: {len(content)} items")
            except Exception as e:
                logging.error(f"  {source_config.type} failed: {e}")
                continue

        # Step 2: Deduplicate
        existing_urls = self.strapi.get_article_urls(days=7)
        new_content = [c for c in all_content if c.source_url not in existing_urls]
        logging.info(f"  Dedup: {len(new_content)} new (was {len(all_content)})")

        # Step 3: AI Processing
        processed = []
        for content in new_content:
            try:
                result = self.summarizer.summarize_article(
                    content.title,
                    content.body,
                    game.name,
                    'news'  # Could be classified from content
                )
                processed.append((content, result))
            except Exception as e:
                logging.error(f"  AI failed for {content.title}: {e}")
                continue

        # Step 4: Rank and select top 10
        ranked = sorted(processed, key=lambda x: x[1]['relevanceScore'], reverse=True)
        top_10 = ranked[:10]
        logging.info(f"  Ranked: Top 10 selected from {len(processed)}")

        # Step 5: Push to Strapi
        game_entity = self.strapi.get_game_by_slug(game.slug)
        if not game_entity:
            logging.error(f"  Game {game.slug} not found in Strapi!")
            return

        for content, ai_result in top_10:
            try:
                article_data = {
                    'title': content.title,
                    'summary': ai_result['summary'],
                    'body': ai_result['body'],
                    'contentType': ai_result['contentType'],
                    'sourceUrl': content.source_url,
                    'sourceName': content.source_name,
                    'originalAuthor': content.original_author,
                    'videoUrl': content.video_url,
                    'scrapedAt': content.scraped_at,
                    'expiresAt': (datetime.now() + timedelta(days=7)).isoformat(),
                    'priority': 'normal',
                }

                draft = self.strapi.create_draft_article(article_data, game_entity['id'])
                logging.info(f"  Created draft: {content.title}")

                # Upload thumbnail
                if content.image_url or content.youtube_video_id:
                    download_and_upload_thumbnail(
                        draft['data']['id'],
                        content.image_url,
                        content.youtube_video_id,
                        self.strapi
                    )
            except Exception as e:
                logging.error(f"  Failed to create article: {e}")
                continue

        logging.info(f"  {game.name}: Created {len(top_10)} drafts")

def main():
    """CLI entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    orchestrator = ContentOrchestrator()
    orchestrator.run_for_all_games()

if __name__ == '__main__':
    main()
```

Deliverables:
- src/orchestrator.py (300-400 lines)
- CLI entry point
- Comprehensive logging
- Error handling

Acceptance:
- Can process all 6 games
- Each game gets ~10 drafts
- Failures don't crash pipeline
- Clear logs show progress
```

#### M3.2: Create Remaining Game Configs (4-6 hours)

```yaml
# Create 5 more game config files

Tasks:
- [ ] Research and populate source URLs for:
  - free-fire.yaml
  - brawl-stars.yaml
  - mobile-legends.yaml
  - pubg-mobile.yaml (can reuse some work from existing scraper knowledge)
  - wild-rift.yaml

- [ ] For each game, find:
  - Official blog URL or RSS feed
  - Subreddit name
  - YouTube channel ID
  - Twitch game category (optional)

- [ ] Seed games in Strapi:
  - Upload icons
  - Create Game entities with source metadata

Deliverables:
- games/free-fire.yaml
- games/brawl-stars.yaml
- games/mobile-legends.yaml
- games/pubg-mobile.yaml
- games/wild-rift.yaml
- 5 games seeded in Strapi

Acceptance:
- All 6 game configs valid YAML
- All games in Strapi database
- Can query GET /api/games and see all 6
```

#### M3.3: Adapt Cleanup Job (2-3 hours)

```python
# Modify src/cleanup.py

Tasks:
- [ ] Change from SQLite to Strapi API
- [ ] Change from 30-day delete to 7-day unpublish
- [ ] Implement unpublish logic (set publishedAt = null)
- [ ] Schedule: Run daily alongside scraper

Example:
```python
def cleanup_expired_articles():
    """Unpublish articles older than 7 days"""
    strapi = StrapiClient(
        os.getenv('STRAPI_URL'),
        os.getenv('STRAPI_TOKEN')
    )

    cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()

    # Find expired published articles
    params = {
        'filters': {
            'publishedAt': {'$notNull': True},
            'expiresAt': {'$lt': cutoff_date}
        }
    }

    articles = strapi.get_articles(params)

    logging.info(f"Found {len(articles)} expired articles to unpublish")

    for article in articles:
        strapi.unpublish_article(article['id'])
        logging.info(f"Unpublished: {article['attributes']['title']}")

    logging.info(f"Cleanup complete: {len(articles)} unpublished")

if __name__ == '__main__':
    cleanup_expired_articles()
```

Deliverables:
- Updated src/cleanup.py
- 7-day unpublish logic
- Logging

Acceptance:
- Articles older than 7 days are unpublished
- Unpublished articles not visible in app
- Can be run manually or scheduled
```

#### M3.4: Update Verification System (2-3 hours)

```python
# Modify src/verify_system.py

Tasks:
- [ ] Add Strapi connectivity test
- [ ] Add game config validation test
- [ ] Add source scraper tests (can connect to APIs)
- [ ] Keep existing tests where applicable

New Tests:
```python
def test_strapi_connection():
    """Test: Can connect to Strapi"""
    strapi = StrapiClient(...)
    try:
        games = strapi.get_games()
        print("✅ Strapi connection: OK")
        print(f"   Games found: {len(games)}")
        return True
    except Exception as e:
        print(f"❌ Strapi connection: FAILED - {e}")
        return False

def test_game_configs():
    """Test: All game configs are valid"""
    try:
        games = GameConfig.load_all('games/')
        print(f"✅ Game configs: {len(games)} loaded")
        for game in games:
            print(f"   - {game.name}: {len(game.sources)} sources")
        return True
    except Exception as e:
        print(f"❌ Game configs: FAILED - {e}")
        return False

def test_reddit_api():
    """Test: Reddit API credentials work"""
    try:
        reddit = praw.Reddit(...)
        subreddit = reddit.subreddit('CoDMCompetitive')
        list(subreddit.hot(limit=1))
        print("✅ Reddit API: OK")
        return True
    except Exception as e:
        print(f"❌ Reddit API: FAILED - {e}")
        return False

# Similar for YouTube API, Twitch API
```

Deliverables:
- Updated src/verify_system.py
- New tests for Strapi and sources
- Comprehensive validation

Acceptance:
- 25+ tests covering all components
- All tests pass on properly configured system
- Clear error messages when things fail
```

---

### Phase 4: Deployment & Testing

**Duration**: 2-3 days (16-20 hours)
**Dependencies**: Phase 3 complete
**Parallelizable**: Partially

#### M4.1: GitHub Actions Workflow (4-5 hours)

``yaml
# .github/workflows/scrape.yml

Tasks:
- [ ] Create workflow file
- [ ] Configure secrets
- [ ] Test manual trigger
- [ ] Test scheduled trigger
- [ ] Add error notification (Discord webhook)

Workflow:
```yaml
name: Daily Content Scrape

on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC daily
  workflow_dispatch:      # Manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run orchestrator
        env:
          STRAPI_URL: ${{ secrets.STRAPI_URL }}
          STRAPI_TOKEN: ${{ secrets.STRAPI_TOKEN }}
          REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
          REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python -m src.orchestrator

      - name: Run cleanup job
        env:
          STRAPI_URL: ${{ secrets.STRAPI_URL }}
          STRAPI_TOKEN: ${{ secrets.STRAPI_TOKEN }}
        run: |
          python -m src.cleanup

      - name: Notify on failure
        if: failure()
        run: |
          curl -H "Content-Type: application/json" \
            -d '{"content":"❌ Content scraper FAILED - check GitHub Actions logs"}' \
            ${{ secrets.DISCORD_WEBHOOK_URL }}
```

Deliverables:
- .github/workflows/scrape.yml
- GitHub Secrets configured
- Documentation for adding secrets

Acceptance:
- Manual trigger works
- Scheduled trigger would work (test with cron in 5 min)
- Failure notification sent to Discord
- Logs show clear progress
```

#### M4.2: Pilot Test - CoD Mobile Only (4-6 hours)

```markdown
Tasks:
- [ ] Configure only cod-mobile.yaml with known-good sources
- [ ] Run orchestrator for CoD Mobile only
- [ ] Verify 10 drafts created in Strapi
- [ ] Manually review drafts in Strapi UI
- [ ] Approve and publish 3 articles
- [ ] Verify published articles visible in API
- [ ] Verify drafts not visible in API
- [ ] Check thumbnails uploaded correctly
- [ ] Verify AI summaries are good quality

Test Command:
```bash
# Temporarily modify orchestrator to only process cod-mobile
python -m src.orchestrator --game cod-mobile

# Or modify orchestrator.py to have:
# games = [GameConfig.load('games/cod-mobile.yaml')]
```

Acceptance Criteria:
- [ ] 10 draft articles in Strapi for CoD Mobile
- [ ] All have reviewStatus = "pending"
- [ ] None are published (publishedAt = null)
- [ ] Summaries are ≤150 chars
- [ ] Bodies are 1-2 paragraphs
- [ ] Thumbnails present and working
- [ ] Can approve and publish in Strapi UI
- [ ] Published articles appear in API
- [ ] GET /api/articles?filters[game][slug]=cod-mobile works

Success Metrics:
- [ ] Admin can review all 10 drafts in <2 minutes
- [ ] At least 8/10 drafts are good quality (don't need editing)
- [ ] No crashes or errors in logs
```

#### M4.3: Full 6-Game Test (4-6 hours)

```markdown
Tasks:
- [ ] Enable all 6 game configs
- [ ] Run full orchestrator
- [ ] Verify ~60 drafts created (10 per game)
- [ ] Check distribution (each game has 10)
- [ ] Spot-check quality across games
- [ ] Monitor API costs
- [ ] Check execution time (should be <30 min)

Test Command:
```bash
python -m src.orchestrator
```

Acceptance Criteria:
- [ ] ~60 draft articles in Strapi
- [ ] Each game has ~10 drafts
- [ ] No game failed completely
- [ ] Total execution time <30 minutes
- [ ] Claude API cost <$2 for full run
- [ ] No rate limit errors
- [ ] All thumbnails uploaded
- [ ] No duplicate articles (same sourceUrl)

Success Metrics:
- [ ] 90%+ of drafts are good quality
- [ ] Admin can review all 60 in <15 minutes
- [ ] No critical errors in logs
```

#### M4.4: Documentation (2-3 hours)

```markdown
Tasks:
- [ ] Create STRAPI_SETUP_GUIDE.md
  - How to set up Strapi Cloud account
  - How to create content types
  - How to seed games
  - How to configure Cloudinary

- [ ] Create API_CREDENTIALS_GUIDE.md
  - Reddit API: How to get client ID/secret
  - YouTube API: How to get API key
  - Anthropic API: How to get Claude key
  - Strapi: How to generate API token

- [ ] Update README.md
  - New architecture diagram
  - Quick start for SwipePads pipeline
  - Link to setup guides

- [ ] Create ADMIN_GUIDE.md
  - How to review content in Strapi
  - How to approve/reject articles
  - How to publish articles
  - What to look for when reviewing

Deliverables:
- STRAPI_SETUP_GUIDE.md
- API_CREDENTIALS_GUIDE.md
- ADMIN_GUIDE.md
- Updated README.md

Acceptance:
- Non-technical person can follow guides
- All steps documented with screenshots
- Links to external resources provided
```

---

## 4. Parallelization Strategy

### What Can Run in Parallel

```
TIME →

Week 1:
├─ Phase 0 (Sequential) ──────────────┐
│  M0.1: Strapi setup               │
│  M0.2: Content types              │
│  M0.3: Seed test game             │
│  M0.4: Project structure          │
│  M0.5: Environment config         │
└───────────────────────────────────┘

Week 1-2:
├─ Phase 1 (Mostly Sequential) ──────┐
│  M1.1: Strapi API client          │
│  M1.2: Game config system         │
│  ├─ M1.3: AI summarization ◄──────┼── Can overlap
│  └─ M1.4: Image pipeline  ◄───────┘
└───────────────────────────────────┘

Week 2-3:
├─ Phase 2 (PARALLEL) ───────────────┐
│  ┌─ M2.1: Reddit scraper          │ ◄─┐
│  ├─ M2.2: YouTube scraper         │ ◄─┼─ All independent!
│  ├─ M2.3: Blog scraper            │ ◄─┤
│  └─ M2.4: Twitch scraper (opt)    │ ◄─┘
│  M2.5: Source factory (after)     │
└───────────────────────────────────┘

Week 3-4:
├─ Phase 3 (Sequential) ─────────────┐
│  M3.1: Orchestrator               │
│  M3.2: Game configs               │
│  M3.3: Cleanup job                │
│  M3.4: Verification system        │
└───────────────────────────────────┘

Week 4:
├─ Phase 4 (Partially Parallel) ────┐
│  M4.1: GitHub Actions             │
│  ├─ M4.2: Pilot test ◄────────────┼── Can overlap
│  └─ M4.4: Documentation ◄─────────┘
│  M4.3: Full test (after pilot)    │
└───────────────────────────────────┘
```

### Parallel Work Opportunities

**If working alone**:
- Focus on one phase at a time
- Within Phase 2, build one scraper fully before starting next

**If working with a team**:
- Developer A: Reddit + YouTube scrapers
- Developer B: Blog + Twitch scrapers
- Both merge when done

**If using AI agent**:
- Agent can work on multiple Phase 2 files simultaneously
- Each scraper is ~150-200 lines, very self-contained

---

## 5. Dependency Map

```
Phase 0: Foundation
   │
   ├──> Phase 1: Integration Layer
   │       │
   │       └──> Phase 2: Source Scrapers (PARALLEL)
   │               │
   │               └──> Phase 3: Orchestration
   │                       │
   │                       └──> Phase 4: Deployment
   │
   └──> (Can start Phase 2 work early if interface defined)

Critical Path:
P0 → P1.1 (Strapi client) → P3.1 (Orchestrator) → P4.2 (Pilot) → P4.3 (Full test)

Parallel Streams:
- P1.3 + P1.4 (AI + Images) can overlap
- P2.1 + P2.2 + P2.3 + P2.4 (All scrapers) fully parallel
- P4.2 + P4.4 (Pilot + Docs) can overlap
```

---

## 6. Effort Estimates

### By Phase

| Phase | Duration | Hours | Parallelizable |
|-------|----------|-------|----------------|
| Phase 0: Foundation | 2-3 days | 16-20 | No |
| Phase 1: Integration | 3-4 days | 20-28 | Partial (2 tasks) |
| Phase 2: Scrapers | 1-2 weeks | 30-50 | YES (4 tasks) |
| Phase 3: Orchestration | 3-4 days | 20-28 | No |
| Phase 4: Deployment | 2-3 days | 16-20 | Partial (2 tasks) |
| **TOTAL** | **3-4 weeks** | **102-146** | - |

### By Component

| Component | Lines of Code | Hours | Priority |
|-----------|---------------|-------|----------|
| Strapi Client | 200-300 | 6-8 | P0 |
| Game Config System | 100-150 | 4-5 | P0 |
| AI Summarization (adapt) | 100-150 | 3-4 | P0 |
| Image Uploader (adapt) | 50-100 | 2-3 | P1 |
| Reddit Scraper | 150-200 | 8-10 | P0 |
| YouTube Scraper | 150-200 | 8-10 | P0 |
| Blog Scraper | 200-250 | 6-8 | P0 |
| Twitch Scraper | 150-200 | 6-8 | P2 (optional) |
| Orchestrator | 300-400 | 10-12 | P0 |
| Cleanup Job (adapt) | 50-100 | 2-3 | P1 |
| Verification (adapt) | 100-150 | 2-3 | P1 |
| GitHub Actions | 50-100 | 4-5 | P0 |
| Documentation | - | 6-8 | P1 |
| **TOTAL** | **~2000** | **~70-90** | - |

---

## 7. Risk Assessment

### High Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **API quota limits** | Can't scrape enough content | Use official APIs (high limits), implement caching, monitor usage |
| **Strapi free tier limits** | Cost overrun | Check limits before starting, budget for $29/mo Pro tier if needed |
| **Source scraper complexity** | Takes longer than estimated | Start with Reddit + YouTube (easiest), defer Twitch/Twitter |
| **AI costs higher than expected** | Budget overrun | Use Haiku (cheap), batch process, monitor costs daily |

### Medium Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Game source configs incomplete** | Can't scrape some games | Research sources before starting, defer games with missing sources |
| **Content quality issues** | Admin rejects most drafts | Tune prompts during pilot, add quality filters |
| **Orchestrator bugs** | Pipeline fails mid-run | Comprehensive error handling, continue-on-failure pattern |
| **GitHub Actions timeout** | Workflow fails | Set 60-min timeout, optimize scraping speed |

### Low Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Image upload failures** | Articles without thumbnails | Fallback to game icon, allow missing images |
| **Cleanup job failures** | Old articles not unpublished | Run manually if needed, not critical for MVP |
| **Documentation gaps** | Harder to maintain | Write docs as you build, not at end |

---

## 8. Acceptance Criteria

### Phase-Level Acceptance

**Phase 0 Complete When**:
- [ ] Strapi Cloud accessible at known URL
- [ ] Game and Article content types created
- [ ] 1 test game seeded (CoD Mobile)
- [ ] Can create article manually in Strapi UI
- [ ] API credentials documented
- [ ] Project structure reorganized

**Phase 1 Complete When**:
- [ ] Can create draft article via Python code
- [ ] Can upload thumbnail via Python code
- [ ] Can load game config from YAML
- [ ] AI summarization produces ≤150 char summaries
- [ ] All unit tests pass

**Phase 2 Complete When**:
- [ ] Reddit scraper returns 10+ ScrapedContent items
- [ ] YouTube scraper returns 5+ ScrapedContent items
- [ ] Blog scraper returns 5+ ScrapedContent items
- [ ] All scrapers respect rate limits
- [ ] All unit tests pass

**Phase 3 Complete When**:
- [ ] Orchestrator processes all 6 games without crashing
- [ ] ~60 drafts created in Strapi
- [ ] No duplicate articles
- [ ] Cleanup job unpublishes old articles
- [ ] Verification system passes all tests

**Phase 4 Complete When**:
- [ ] GitHub Actions workflow runs successfully
- [ ] Pilot test (CoD Mobile) succeeds
- [ ] Full test (6 games) succeeds
- [ ] Documentation complete
- [ ] Admin can review and publish content

### Overall Project Acceptance

**Minimum Viable Product** is complete when:

- [ ] 6 games configured with sources
- [ ] Orchestrator runs daily via GitHub Actions
- [ ] Produces ~60 drafts per day (10 per game)
- [ ] Admin can review in Strapi UI (reviewStatus filter)
- [ ] Admin can approve and publish (~15 minutes total)
- [ ] Published articles appear in API
- [ ] Draft/rejected articles hidden from API
- [ ] Articles auto-expire after 7 days
- [ ] Total cost ≤$70/month
- [ ] No manual intervention needed (runs autonomously)
- [ ] Documentation allows handoff to team

---

## 9. Next Steps After Approval

Once you approve this plan:

1. **I create Phase 0 tasks** in detail
2. **You decide**: Do you want me to implement or just guide you?
3. **I set up Strapi Cloud** with you (step-by-step walkthrough)
4. **We start building** Phase 0 → Phase 1 → Phase 2...
5. **Regular check-ins** after each milestone

**Questions before starting**:
1. Does this plan make sense?
2. Any phases you want me to modify?
3. Do you want me to code this or guide you through it?
4. Should I prioritize different components?
5. Any budget/timeline constraints I should know?

---

**END OF IMPLEMENTATION PLAN**

This is a comprehensive, executable plan. Ready to proceed when you are!
