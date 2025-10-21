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
    def validate(cls):
        """
        Validate that required configuration is present.
        Returns tuple: (is_valid, error_message)
        """
        # Check that at least one API key is configured
        if not cls.ANTHROPIC_API_KEY and not cls.OPENAI_API_KEY:
            return False, "No AI API key configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"

        # Validate that keys don't have placeholder values
        if cls.ANTHROPIC_API_KEY and 'your_' in cls.ANTHROPIC_API_KEY.lower():
            return False, "ANTHROPIC_API_KEY contains placeholder value. Please update .env with real key."

        if cls.OPENAI_API_KEY and 'your_' in cls.OPENAI_API_KEY.lower():
            return False, "OPENAI_API_KEY contains placeholder value. Please update .env with real key."

        return True, "Configuration valid"

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
