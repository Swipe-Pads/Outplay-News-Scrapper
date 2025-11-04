"""
AI-powered article summarization module.

This module uses Anthropic Claude API to generate concise summaries
of news articles (3-5 bullet points, 200-300 characters).
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from typing import Optional, Dict
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from src.config import Config

# Set up logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    """Base exception for summarization errors."""
    pass


class APIKeyError(SummarizationError):
    """Exception raised when API key is missing or invalid."""
    pass


class CostTracker:
    """
    Track API usage costs.

    Claude 3.5 Sonnet pricing (as of Oct 2024):
    - Input: $3 per million tokens
    - Output: $15 per million tokens
    """

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

    def add_usage(self, input_tokens: int, output_tokens: int):
        """Record token usage from a request."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_requests += 1

    def get_cost_estimate(self) -> Dict[str, float]:
        """
        Calculate estimated cost in USD.

        Returns:
            Dictionary with input_cost, output_cost, and total_cost
        """
        input_cost = (self.total_input_tokens / 1_000_000) * 3.0
        output_cost = (self.total_output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'input_cost': round(input_cost, 4),
            'output_cost': round(output_cost, 4),
            'total_cost': round(total_cost, 4),
            'requests': self.total_requests
        }

    def __str__(self):
        """String representation of cost tracker."""
        stats = self.get_cost_estimate()
        return (
            f"API Usage: {stats['requests']} requests, "
            f"{stats['input_tokens']} input tokens, "
            f"{stats['output_tokens']} output tokens, "
            f"${stats['total_cost']:.4f} total"
        )


# Global cost tracker
cost_tracker = CostTracker()


def get_client() -> Anthropic:
    """
    Get configured Anthropic API client.

    Returns:
        Anthropic client instance

    Raises:
        APIKeyError: If API key is not configured
    """
    # Validate Anthropic configuration specifically
    is_valid, error_msg = Config.validate(provider='anthropic')
    if not is_valid:
        raise APIKeyError(error_msg)

    try:
        client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        return client
    except Exception as e:
        raise APIKeyError(f"Failed to initialize Anthropic client: {e}")


def test_connection() -> bool:
    """
    Test connection to Anthropic API.

    Returns:
        True if connection successful

    Raises:
        APIKeyError: If API key is invalid
        SummarizationError: If connection fails
    """
    try:
        client = get_client()

        logger.info("Testing connection to Anthropic API...")

        # Send a simple test prompt
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[
                {"role": "user", "content": "Say 'Connection successful' and nothing else."}
            ]
        )

        # Track usage
        cost_tracker.add_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )

        logger.info(f"✅ Connected to Anthropic API")
        logger.info(f"✅ Model: {response.model}")
        logger.info(f"✅ Test completion successful")
        logger.info(f"   Usage: {response.usage.input_tokens} input tokens, "
                   f"{response.usage.output_tokens} output tokens")

        return True

    except APIConnectionError as e:
        logger.error(f"Connection error: {e}")
        raise SummarizationError(f"Failed to connect to Anthropic API: {e}")
    except RateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        raise SummarizationError(f"API rate limit exceeded: {e}")
    except APIError as e:
        logger.error(f"API error: {e}")
        raise SummarizationError(f"Anthropic API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise SummarizationError(f"Unexpected error during API test: {e}")


def summarize_article(
    title: str,
    content: str,
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 300
) -> str:
    """
    Generate a concise summary of an article.

    Args:
        title: Article title
        content: Full article content
        model: Claude model to use (default: claude-3-5-sonnet-20241022)
        max_tokens: Maximum tokens for summary (default: 300)

    Returns:
        Summary as string (3-5 bullet points, 200-300 characters)

    Raises:
        SummarizationError: If summarization fails
    """
    try:
        client = get_client()

        # Construct prompt for summarization
        prompt = f"""Please summarize the following news article in 3-5 concise bullet points.
The entire summary should be 200-300 characters total.
Focus on the key information that would interest busy mobile game enthusiasts.

Title: {title}

Content:
{content[:2000]}

Format your response as bullet points (use • for bullets), with each point being a short, punchy statement."""

        logger.info(f"Generating summary for: {title[:50]}...")

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Track usage
        cost_tracker.add_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )

        # Extract summary text
        summary = response.content[0].text.strip()

        logger.info(f"✅ Summary generated ({len(summary)} chars)")
        logger.info(f"   Usage: {response.usage.input_tokens} input tokens, "
                   f"{response.usage.output_tokens} output tokens")

        return summary

    except APIConnectionError as e:
        logger.error(f"Connection error: {e}")
        raise SummarizationError(f"Failed to connect to Anthropic API: {e}")
    except RateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        raise SummarizationError(f"API rate limit exceeded: {e}")
    except APIError as e:
        logger.error(f"API error: {e}")
        raise SummarizationError(f"Anthropic API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise SummarizationError(f"Unexpected error during summarization: {e}")


if __name__ == '__main__':
    """
    Test the summarizer module.
    """
    print("=" * 60)
    print("Testing Anthropic API Connection")
    print("=" * 60)
    print()

    try:
        # Test connection
        test_connection()
        print()
        print("✅ Connection test passed!")
        print()

        # Show cost tracker
        print("=" * 60)
        print("Cost Tracker")
        print("=" * 60)
        print(cost_tracker)
        print()

        # Test summarization with sample text
        print("=" * 60)
        print("Testing Summarization")
        print("=" * 60)
        print()

        sample_title = "Backbone teams with PlayStation for new Death Stranding 2-themed controller"
        sample_content = """
        Backbone has announced a new partnership with PlayStation to create a
        special edition controller themed around Death Stranding 2. The controller
        features custom artwork inspired by the game's post-apocalyptic setting
        and will be available for pre-order starting next month. The device is
        compatible with both iOS and Android devices and includes all of Backbone's
        signature features like low-latency gameplay and a dedicated app for
        content capture and streaming.
        """

        summary = summarize_article(sample_title, sample_content)

        print(f"Title: {sample_title}")
        print()
        print("Summary:")
        print("-" * 60)
        print(summary)
        print("-" * 60)
        print()

        # Final cost report
        print("=" * 60)
        print("Final Cost Report")
        print("=" * 60)
        print(cost_tracker)
        print()

        costs = cost_tracker.get_cost_estimate()
        print(f"Total cost: ${costs['total_cost']:.4f}")
        print()
        print("✅ All tests passed!")

    except APIKeyError as e:
        print(f"❌ API Key Error: {e}")
        print()
        print("Please configure ANTHROPIC_API_KEY in .env file")
        sys.exit(1)
    except SummarizationError as e:
        print(f"❌ Summarization Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        sys.exit(1)
