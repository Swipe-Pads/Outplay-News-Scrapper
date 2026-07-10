"""
AI-powered article summarization module.

Uses Anthropic Claude API to generate concise summaries
of news articles (3-5 bullet points, 200-300 characters).
"""

import time
import logging
from typing import Optional, Dict, List
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from src.config import Config

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
        self.reset()

    def reset(self):
        """Reset all counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

    def add_usage(self, input_tokens: int, output_tokens: int):
        """Record token usage from a request."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_requests += 1

    def get_cost_estimate(self) -> Dict[str, float]:
        """Calculate estimated cost in USD."""
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
        stats = self.get_cost_estimate()
        return (
            f"API Usage: {stats['requests']} requests, "
            f"{stats['input_tokens']} input tokens, "
            f"{stats['output_tokens']} output tokens, "
            f"${stats['total_cost']:.4f} total"
        )


cost_tracker = CostTracker()


def get_client() -> Anthropic:
    """Get configured Anthropic API client."""
    is_valid, error_msg = Config.validate(provider='anthropic')
    if not is_valid:
        raise APIKeyError(error_msg)

    try:
        return Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    except Exception as e:
        raise APIKeyError(f"Failed to initialize Anthropic client: {e}")


def test_connection() -> bool:
    """Test connection to Anthropic API."""
    try:
        client = get_client()
        logger.info("Testing connection to Anthropic API...")

        response = client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=50,
            thinking={"type": "disabled"},
            messages=[
                {"role": "user", "content": "Say 'Connection successful' and nothing else."}
            ]
        )

        cost_tracker.add_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )

        logger.info(f"Connected to Anthropic API (model: {response.model})")
        return True

    except APIConnectionError as e:
        raise SummarizationError(f"Failed to connect to Anthropic API: {e}")
    except RateLimitError as e:
        raise SummarizationError(f"API rate limit exceeded: {e}")
    except APIError as e:
        raise SummarizationError(f"Anthropic API error: {e}")


def summarize_article(
    title: str,
    content: str,
    max_tokens: int = 300,
    max_retries: int = 3
) -> str:
    """
    Generate a concise summary of an article with rate limiting and retry.

    Args:
        title: Article title
        content: Full article content
        max_tokens: Maximum tokens for summary
        max_retries: Max retries on rate limit errors

    Returns:
        Summary as string (3-5 bullet points, 200-300 characters)
    """
    client = get_client()

    prompt = f"""Summarize this mobile gaming news article in 3-5 concise bullet points.
Total summary should be 200-300 characters. Focus on key info for busy mobile game enthusiasts.

Title: {title}

Content:
{content[:2000]}

Use bullet format with the dot character for bullets. Each point should be short and punchy."""

    for attempt in range(max_retries):
        try:
            # Rate limit between API calls
            if attempt > 0 or cost_tracker.total_requests > 0:
                time.sleep(Config.API_RATE_LIMIT_SECONDS)

            logger.info(f"Generating summary for: {title[:50]}...")

            response = client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=max_tokens,
                # short article summaries: no thinking needed (Sonnet 5 defaults to adaptive)
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}]
            )

            cost_tracker.add_usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            summary = next(b.text for b in response.content if b.type == "text").strip()
            logger.info(f"Summary generated ({len(summary)} chars)")
            return summary

        except RateLimitError as e:
            wait_time = Config.API_RATE_LIMIT_SECONDS * (2 ** attempt)
            logger.warning(f"Rate limited, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
            if attempt == max_retries - 1:
                raise SummarizationError(f"API rate limit exceeded after {max_retries} retries: {e}")

        except APIConnectionError as e:
            raise SummarizationError(f"Failed to connect to Anthropic API: {e}")
        except APIError as e:
            raise SummarizationError(f"Anthropic API error: {e}")


def summarize_batch(
    articles: List[dict],
    db_path: str = None
) -> Dict[str, any]:
    """
    Summarize multiple articles with rate limiting.

    Args:
        articles: List of article dicts (must have 'url', 'title', 'content')
        db_path: If provided, save summaries to DB after each one

    Returns:
        Stats dict with success/failed/skipped counts
    """
    from src.database import update_article_summary

    stats = {
        'total': len(articles),
        'success': 0,
        'failed': 0,
        'skipped': 0,
    }

    for idx, article in enumerate(articles, 1):
        title = article.get('title', '')
        content = article.get('content', '')
        url = article.get('url', '')

        if not content:
            logger.info(f"[{idx}/{stats['total']}] Skipped (no content): {title[:50]}")
            stats['skipped'] += 1
            continue

        try:
            summary = summarize_article(title, content)

            if db_path and url:
                update_article_summary(url, summary, db_path)
                logger.info(f"[{idx}/{stats['total']}] Summarized and saved: {title[:50]}")
            else:
                logger.info(f"[{idx}/{stats['total']}] Summarized: {title[:50]}")

            stats['success'] += 1

        except SummarizationError as e:
            logger.error(f"[{idx}/{stats['total']}] Failed: {title[:50]} — {e}")
            stats['failed'] += 1
        except Exception as e:
            logger.error(f"[{idx}/{stats['total']}] Unexpected error: {e}")
            stats['failed'] += 1

    logger.info(f"Batch summarization complete: {stats['success']} success, "
                f"{stats['failed']} failed, {stats['skipped']} skipped")
    logger.info(f"Cost: {cost_tracker}")

    return stats


if __name__ == '__main__':
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Testing Anthropic API Connection")
    print("=" * 60)

    try:
        test_connection()
        print(f"Connection test passed! Model: {Config.CLAUDE_MODEL}")
        print(f"Cost: {cost_tracker}")

        sample_title = "Backbone teams with PlayStation for new Death Stranding 2-themed controller"
        sample_content = """
        Backbone has announced a new partnership with PlayStation to create a
        special edition controller themed around Death Stranding 2. The controller
        features custom artwork inspired by the game's post-apocalyptic setting
        and will be available for pre-order starting next month.
        """

        summary = summarize_article(sample_title, sample_content)
        print(f"\nSummary:\n{summary}")
        print(f"\nFinal cost: {cost_tracker}")

    except APIKeyError as e:
        print(f"API Key Error: {e}")
        sys.exit(1)
    except SummarizationError as e:
        print(f"Summarization Error: {e}")
        sys.exit(1)
