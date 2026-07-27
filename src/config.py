"""
Configuration module for SwipePads News Scraper.
Loads settings from environment variables using python-dotenv.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# Look for .env in project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / '.env'

load_dotenv(dotenv_path=ENV_PATH)


class Config:
    """
    Configuration class that loads all settings from environment variables.

    Usage:
        from src.config import Config
        print(Config.USER_AGENT)
    """

    # API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

    # Scraper Settings
    USER_AGENT = os.getenv('SCRAPER_USER_AGENT', 'SwipePadsScraper/1.0')
    RATE_LIMIT_SECONDS = int(os.getenv('SCRAPER_RATE_LIMIT_SECONDS', '2'))

    # AI Settings
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-5')
    API_RATE_LIMIT_SECONDS = float(os.getenv('API_RATE_LIMIT_SECONDS', '1.0'))

    # YouTube API
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
    YOUTUBE_MAX_RESULTS = int(os.getenv('YOUTUBE_MAX_RESULTS', '10'))

    # Reddit API
    REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID', '')
    REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', '')
    REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'OutplayNewsScraper/1.0')
    REDDIT_MIN_SCORE = int(os.getenv('REDDIT_MIN_SCORE', '5'))

    # Strapi CMS
    STRAPI_URL = os.getenv('STRAPI_URL', 'http://localhost:1337')
    STRAPI_API_TOKEN = os.getenv('STRAPI_API_TOKEN', '')
    STRAPI_PUBLISH = os.getenv('STRAPI_PUBLISH', 'false').lower() == 'true'

    # Shopify blog publishing (weekly digest drafts)
    SHOPIFY_STORE_DOMAIN = os.getenv('SHOPIFY_STORE_DOMAIN', '')
    SHOPIFY_CLIENT_ID = os.getenv('SHOPIFY_CLIENT_ID', '')
    SHOPIFY_CLIENT_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET', '')
    SHOPIFY_ADMIN_TOKEN = os.getenv('SHOPIFY_ADMIN_TOKEN', '')  # optional static fallback
    SHOPIFY_BLOG_ID = os.getenv('SHOPIFY_BLOG_ID', '')

    # Cloudflare Email Service (weekly digest mailing)
    CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID', '')
    CF_EMAIL_API_TOKEN = os.getenv('CF_EMAIL_API_TOKEN', '')  # scope: Email Sending Send
    CF_KV_API_TOKEN = os.getenv('CF_KV_API_TOKEN', '')  # scope: Workers KV read (falls back to email token)
    KV_NAMESPACE_ID = os.getenv('KV_NAMESPACE_ID', '')  # unsubscribe suppression list
    MAIL_FROM = os.getenv('MAIL_FROM', '')
    MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', 'SwipePads Weekly')
    MAIL_RATE_PER_SEC = float(os.getenv('MAIL_RATE_PER_SEC', '5'))
    UNSUBSCRIBE_BASE_URL = os.getenv('UNSUBSCRIBE_BASE_URL', '')
    UNSUB_SECRET = os.getenv('UNSUB_SECRET', '')

    # Newsletter inbox (news.outplay.game -> newsletter-inbox Worker -> KV)
    NEWSLETTER_KV_NAMESPACE_ID = os.getenv('NEWSLETTER_KV_NAMESPACE_ID', '')
    NEWSLETTER_SINCE_DAYS = float(os.getenv('NEWSLETTER_SINCE_DAYS', '8'))

    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/articles.db')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/scraper.log')

    # Retention
    ARTICLE_RETENTION_DAYS = int(os.getenv('ARTICLE_RETENTION_DAYS', '30'))

    # Derived paths (relative to project root)
    DATABASE_FULL_PATH = PROJECT_ROOT / DATABASE_PATH
    LOG_FILE_FULL_PATH = PROJECT_ROOT / LOG_FILE

    @classmethod
    def validate(cls, provider=None):
        """
        Validate that required configuration is present.

        Args:
            provider: Specific provider to validate ('anthropic', 'openai', or None for any)

        Returns tuple: (is_valid, error_message)
        """
        # If no provider specified, check that at least one is valid
        if provider is None:
            has_anthropic = cls.ANTHROPIC_API_KEY and 'your_' not in cls.ANTHROPIC_API_KEY.lower()
            has_openai = cls.OPENAI_API_KEY and 'your_' not in cls.OPENAI_API_KEY.lower()

            if not has_anthropic and not has_openai:
                return False, "No valid AI API key configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"

            return True, "Configuration valid"

        # Validate specific provider
        if provider == 'anthropic':
            if not cls.ANTHROPIC_API_KEY:
                return False, "ANTHROPIC_API_KEY not set in .env"
            if 'your_' in cls.ANTHROPIC_API_KEY.lower():
                return False, "ANTHROPIC_API_KEY contains placeholder value. Please update .env with real key."
            return True, "Anthropic API key valid"

        if provider == 'openai':
            if not cls.OPENAI_API_KEY:
                return False, "OPENAI_API_KEY not set in .env"
            if 'your_' in cls.OPENAI_API_KEY.lower():
                return False, "OPENAI_API_KEY contains placeholder value. Please update .env with real key."
            return True, "OpenAI API key valid"

        return False, f"Unknown provider: {provider}"

    @classmethod
    def get_ai_provider(cls):
        """
        Determine which AI provider to use based on available keys.
        Returns: 'anthropic', 'openai', or None
        """
        if cls.ANTHROPIC_API_KEY and 'your_' not in cls.ANTHROPIC_API_KEY.lower():
            return 'anthropic'
        elif cls.OPENAI_API_KEY and 'your_' not in cls.OPENAI_API_KEY.lower():
            return 'openai'
        return None


# For convenience, export Config as default
__all__ = ['Config']
