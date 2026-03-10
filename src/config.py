"""
Configuration management for the Outplay News Scraper.
Loads settings from .env file and exposes as class properties.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """Application configuration loaded from environment variables."""

    # Project paths
    PROJECT_ROOT = PROJECT_ROOT
    DATA_DIR = PROJECT_ROOT / "data"
    IMAGES_DIR = PROJECT_ROOT / "images"
    EXPORTS_DIR = PROJECT_ROOT / "exports"
    LOGS_DIR = PROJECT_ROOT / "logs"
    GAMES_DIR = PROJECT_ROOT / "games"

    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "articles.db"))

    # Scraper settings
    USER_AGENT = os.getenv("SCRAPER_USER_AGENT", "OutplayNewsScraper/1.0")
    RATE_LIMIT_SECONDS = float(os.getenv("SCRAPER_RATE_LIMIT_SECONDS", "2"))

    # AI API
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Strapi Cloud
    STRAPI_URL = os.getenv("STRAPI_URL", "")
    STRAPI_TOKEN = os.getenv("STRAPI_TOKEN", "")

    # Reddit API
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")

    # YouTube API
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

    # Twitch API (future)
    TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
    TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")

    # Google Trends API (v1alpha)
    GOOGLE_TRENDS_SERVICE_ACCOUNT = os.getenv("GOOGLE_TRENDS_SERVICE_ACCOUNT", "")
    GOOGLE_TRENDS_CREDENTIALS = os.getenv("GOOGLE_TRENDS_CREDENTIALS", "")
    GOOGLE_TRENDS_TOKEN = os.getenv("GOOGLE_TRENDS_TOKEN", "")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", str(LOGS_DIR / "scraper.log"))

    # Content settings
    ARTICLE_RETENTION_DAYS = int(os.getenv("ARTICLE_RETENTION_DAYS", "30"))
    CONTENT_EXPIRY_DAYS = int(os.getenv("CONTENT_EXPIRY_DAYS", "7"))
    MAX_ARTICLES_PER_GAME = int(os.getenv("MAX_ARTICLES_PER_GAME", "10"))

    @classmethod
    def validate(cls) -> list:
        """Validate configuration. Returns list of warnings."""
        warnings = []

        if not cls.ANTHROPIC_API_KEY or cls.ANTHROPIC_API_KEY.startswith("sk-ant-api03-xxx"):
            warnings.append("ANTHROPIC_API_KEY not configured")

        if not cls.STRAPI_URL:
            warnings.append("STRAPI_URL not configured")
        if not cls.STRAPI_TOKEN:
            warnings.append("STRAPI_TOKEN not configured")

        if not cls.REDDIT_CLIENT_ID:
            warnings.append("REDDIT_CLIENT_ID not configured (Reddit scraper won't work)")
        if not cls.YOUTUBE_API_KEY:
            warnings.append("YOUTUBE_API_KEY not configured (YouTube scraper won't work)")

        return warnings

    @classmethod
    def get_ai_provider(cls) -> str:
        """Detect configured AI provider. Prioritizes Anthropic."""
        if cls.ANTHROPIC_API_KEY and not cls.ANTHROPIC_API_KEY.startswith("sk-ant-api03-xxx"):
            return "anthropic"
        if cls.OPENAI_API_KEY and not cls.OPENAI_API_KEY.startswith("sk-xxx"):
            return "openai"
        return "none"

    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist."""
        for d in [cls.DATA_DIR, cls.IMAGES_DIR, cls.EXPORTS_DIR, cls.LOGS_DIR, cls.GAMES_DIR]:
            d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    Config.ensure_directories()
    warnings = Config.validate()
    if warnings:
        print("⚠️  Configuration warnings:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("✅ Configuration OK")

    print(f"\nProject root: {Config.PROJECT_ROOT}")
    print(f"AI provider: {Config.get_ai_provider()}")
    print(f"Database: {Config.DATABASE_PATH}")
    print(f"Strapi URL: {Config.STRAPI_URL or '(not set)'}")
