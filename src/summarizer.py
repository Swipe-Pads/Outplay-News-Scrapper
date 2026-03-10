"""
Gaming news article summarizer using Anthropic Claude API.

Transforms raw scraped content into structured, Strapi CMS-compatible articles
with professional summaries, body text, content classification, and relevance scoring.

Production-ready module with cost tracking, error handling, and API retry logic.
"""

import json
import logging
import os
import re
import time
from typing import Optional, Dict, Any

import anthropic
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-3-5-haiku-20241022"

# Pricing for Claude 3.5 Haiku (March 2024)
INPUT_COST_PER_MILLION = 0.25  # $0.25 per 1M input tokens
OUTPUT_COST_PER_MILLION = 1.25  # $1.25 per 1M output tokens

# Content constraints
MAX_INPUT_CHARS = 3000
MIN_CONTENT_CHARS = 50
MAX_SUMMARY_CHARS = 150
MIN_BODY_WORDS = 100
MAX_BODY_WORDS = 200


class SummarizationError(Exception):
    """Raised when summarization fails."""
    pass


class APIKeyError(Exception):
    """Raised when API key is missing or invalid."""
    pass


class CostTracker:
    """Track API token usage and costs across summarization requests."""

    def __init__(self):
        """Initialize cost tracker."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.request_count = 0
        self.total_cost = 0.0

    def add_request(self, input_tokens: int, output_tokens: int) -> None:
        """
        Record token usage from an API request.

        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.request_count += 1

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_MILLION
        output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION
        self.total_cost += input_cost + output_cost

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of token usage and costs.

        Returns:
            Dictionary with usage and cost details
        """
        return {
            "request_count": self.request_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "total_cost_usd": round(self.total_cost, 4),
        }

    def reset(self) -> None:
        """Reset all counters."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.request_count = 0
        self.total_cost = 0.0


# Global cost tracker
_cost_tracker = CostTracker()


def get_client() -> anthropic.Anthropic:
    """
    Initialize and return an Anthropic API client.

    Returns:
        Initialized Anthropic client

    Raises:
        APIKeyError: If ANTHROPIC_API_KEY is not set or is placeholder
    """
    if not ANTHROPIC_API_KEY:
        raise APIKeyError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it in .env or as an environment variable."
        )

    if ANTHROPIC_API_KEY.startswith("sk-") is False:
        logger.warning(
            "ANTHROPIC_API_KEY does not start with 'sk-'. "
            "Verify the key is correct."
        )

    try:
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        raise APIKeyError(f"Failed to initialize Anthropic client: {str(e)}")


def test_connection() -> bool:
    """
    Test connectivity to the Anthropic API.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": "Say 'OK' only.",
                }
            ],
        )
        logger.info("API connection test successful")
        return True
    except APIKeyError as e:
        logger.error(f"API key error: {str(e)}")
        return False
    except anthropic.RateLimitError:
        logger.warning("Rate limited during connection test")
        return False
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False


def _clean_title(title: str) -> str:
    """
    Clean and normalize article title.

    Removes Reddit formatting (emojis, brackets), clickbait patterns,
    and excessive capitalization while preserving meaning.

    Args:
        title: Raw article title

    Returns:
        Cleaned title in professional gaming news style
    """
    # Remove common Reddit emojis/formatting
    title = re.sub(r"[🔥💯🎮🚀⚡🎯]", "", title)
    title = re.sub(r"\[LEAK\]|\[RUMOR\]|\[NEWS\]|\[DISCUSSION\]", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\[SPOILER\]|\[OC\]|\[NSFW\]", "", title, flags=re.IGNORECASE)

    # Remove excessive punctuation
    title = re.sub(r"!{2,}", "!", title)
    title = re.sub(r"\?{2,}", "?", title)

    # Fix spacing after removals
    title = re.sub(r"\s+", " ", title).strip()

    # Remove leading/trailing special characters
    title = title.strip("!?-_")

    # Handle ALL CAPS (convert to title case if mostly caps)
    if len(title) > 3 and title.isupper():
        title = title.title()

    return title


def _truncate_content(content: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """
    Truncate content to control API costs.

    Args:
        content: Raw content text
        max_chars: Maximum characters to keep

    Returns:
        Truncated content
    """
    if len(content) <= max_chars:
        return content

    # Try to truncate at a sentence boundary
    truncated = content[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.8:  # If period is in last 20%
        return truncated[:last_period + 1]

    return truncated + "..."


def _validate_response(response_data: Dict[str, Any]) -> bool:
    """
    Validate that response contains all required fields.

    Args:
        response_data: Parsed response dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["title", "summary", "body", "content_type", "relevance_score"]

    # Check all fields exist
    for field in required_fields:
        if field not in response_data:
            logger.error(f"Missing required field: {field}")
            return False

    # Validate content_type
    if response_data["content_type"] not in ["news", "video", "community"]:
        logger.error(f"Invalid content_type: {response_data['content_type']}")
        return False

    # Validate relevance_score
    try:
        score = float(response_data["relevance_score"])
        if not (0.0 <= score <= 1.0):
            logger.error(f"relevance_score out of range: {score}")
            return False
    except (ValueError, TypeError):
        logger.error(f"Invalid relevance_score: {response_data['relevance_score']}")
        return False

    # Validate lengths
    if len(response_data["summary"]) > MAX_SUMMARY_CHARS:
        logger.warning(
            f"Summary exceeds {MAX_SUMMARY_CHARS} chars: "
            f"{len(response_data['summary'])} chars"
        )
        response_data["summary"] = response_data["summary"][:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0]

    body_word_count = len(response_data["body"].split())
    if body_word_count < MIN_BODY_WORDS or body_word_count > MAX_BODY_WORDS:
        logger.warning(
            f"Body word count outside range {MIN_BODY_WORDS}-{MAX_BODY_WORDS}: "
            f"{body_word_count} words"
        )

    return True


def _extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from API response, handling markdown code blocks.

    Args:
        text: Response text potentially containing JSON

    Returns:
        Parsed JSON dictionary or None if extraction fails
    """
    # Try to find JSON in markdown code block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if json_match:
        json_text = json_match.group(1)
    else:
        json_text = text

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        logger.debug(f"Response text: {text[:500]}")
        return None


def _call_api_with_retry(
    client: anthropic.Anthropic,
    user_message: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Optional[Dict[str, Any]]:
    """
    Call Claude API with exponential backoff retry logic.

    Args:
        client: Anthropic client
        user_message: User message to send
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        Parsed JSON response or None if all retries fail
    """
    system_prompt = """You are a professional gaming news editor. Your task is to transform raw,
unpolished article text into clean, structured content suitable for a mobile gaming news app.

You must respond ONLY with valid JSON (no markdown code blocks, no extra text). The JSON must have these fields:
- title: String. A professional gaming news headline. Remove Reddit formatting, emojis, clickbait, and ALL CAPS.
- summary: String. ≤150 characters. Concise preview text for mobile tiles.
- body: String. 1-2 paragraphs, 100-200 words. Factual, active voice, no clickbait. Rewritten for clarity.
- content_type: String. One of: "news", "video", or "community". Classify based on content.
- relevance_score: Float between 0.0 and 1.0. How relevant/important for mobile gamers."""

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ],
            )

            # Track costs
            _cost_tracker.add_request(
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            # Extract and parse JSON
            response_text = response.content[0].text
            parsed = _extract_json_from_response(response_text)

            if parsed is None:
                raise SummarizationError(f"Failed to parse JSON from response")

            return parsed

        except anthropic.RateLimitError as e:
            delay = base_delay * (2 ** attempt)
            logger.warning(
                f"Rate limited (attempt {attempt + 1}/{max_retries}). "
                f"Retrying in {delay}s..."
            )
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                logger.error("Max retries exceeded for rate limit")
                raise SummarizationError(f"Rate limited after {max_retries} attempts") from e

        except anthropic.APIError as e:
            logger.error(f"API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1.0)
            else:
                raise SummarizationError(f"API error after {max_retries} attempts") from e

        except anthropic.APIConnectionError as e:
            logger.error(f"Connection error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2.0)
            else:
                raise SummarizationError(f"Connection failed after {max_retries} attempts") from e

    return None


def process_article(
    title: str,
    content: str,
    source_name: str = "",
    game_name: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Process a raw article through Claude AI summarization.

    Transforms raw scraped content into structured Strapi CMS Article format
    with cleaned title, summary, body, content type classification, and relevance score.

    Args:
        title: Raw article title
        content: Raw article body text
        source_name: Origin of article (e.g., "Reddit r/CoDMCompetitive"), optional
        game_name: Associated game (e.g., "Call of Duty: Mobile"), optional

    Returns:
        Dictionary with keys:
            - title: Cleaned, professional headline (string)
            - summary: ≤150 char preview (string)
            - body: 1-2 paragraphs, 100-200 words (string)
            - content_type: "news" | "video" | "community" (string)
            - relevance_score: 0.0-1.0 importance rating (float)
        Returns None if processing fails

    Example:
        >>> result = process_article(
        ...     title="[LEAK] 🔥 NEW SKIN COMING!!!",
        ...     content="Inside sources reveal...",
        ...     source_name="Reddit r/CoDMCompetitive",
        ...     game_name="Call of Duty: Mobile"
        ... )
        >>> if result:
        ...     print(f"Title: {result['title']}")
        ...     print(f"Relevance: {result['relevance_score']}")
    """
    try:
        # Validate inputs
        if not title or not isinstance(title, str):
            logger.error("Invalid title: must be non-empty string")
            return None

        if not content or not isinstance(content, str):
            logger.error("Invalid content: must be non-empty string")
            return None

        # Handle very short content - just clean title and return minimal data
        if len(content) < MIN_CONTENT_CHARS:
            logger.info(f"Content too short ({len(content)} chars), returning minimal summary")
            cleaned_title = _clean_title(title)
            return {
                "title": cleaned_title,
                "summary": content[:MAX_SUMMARY_CHARS],
                "body": content,
                "content_type": "news",
                "relevance_score": 0.5,
            }

        # Clean title
        cleaned_title = _clean_title(title)

        # Truncate content to control costs
        truncated_content = _truncate_content(content, MAX_INPUT_CHARS)

        # Build context for Claude
        context_parts = []
        if source_name:
            context_parts.append(f"Source: {source_name}")
        if game_name:
            context_parts.append(f"Game: {game_name}")
        context_str = " | ".join(context_parts) if context_parts else ""

        # Construct user message
        user_message = f"""Article to summarize:

Title: {cleaned_title}
{f'Context: {context_str}' if context_str else ''}

Content:
{truncated_content}

Please provide a structured summary matching the required JSON format."""

        # Call API with retries
        client = get_client()
        response_data = _call_api_with_retry(client, user_message)

        if response_data is None:
            logger.error("Failed to get valid response from API")
            return None

        # Validate response
        if not _validate_response(response_data):
            logger.error("Response validation failed")
            return None

        logger.info(
            f"Successfully processed article: {cleaned_title[:50]}... "
            f"(relevance: {response_data['relevance_score']})"
        )

        return response_data

    except APIKeyError as e:
        logger.error(f"API key error: {str(e)}")
        return None
    except SummarizationError as e:
        logger.error(f"Summarization error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in process_article: {str(e)}", exc_info=True)
        return None


def get_cost_summary() -> Dict[str, Any]:
    """
    Get the current cost tracking summary.

    Returns:
        Dictionary with token usage and cost details
    """
    return _cost_tracker.get_summary()


def reset_cost_tracker() -> None:
    """Reset the global cost tracker."""
    _cost_tracker.reset()


def main():
    """
    Main entry point for testing the summarizer module.

    Tests API connection, processes a sample article, and displays results.
    """
    logger.info("=" * 70)
    logger.info("Gaming News Summarizer - Connection Test & Demo")
    logger.info("=" * 70)

    # Test connection
    logger.info("\n[1/3] Testing API connection...")
    if not test_connection():
        logger.error("Failed to connect to Anthropic API. Check your API key.")
        return

    logger.info("Connection successful!")

    # Process sample article
    logger.info("\n[2/3] Processing sample article...")

    sample_title = "[LEAK] 🔥 NEW OPERATOR SKIN COMING TO WARZONE!!! INSANE!!!"
    sample_content = """
    According to leaks from reliable dataminers, a new operator skin is coming to Warzone.
    The skin appears to be inspired by a popular action movie character and features
    a sleek tactical outfit with custom weapon blueprints. Release date is expected within
    the next season update. Players are hyped about the potential crossover opportunity
    with the film franchise. The dataminer suggests additional cosmetics may also release
    alongside the operator. This follows previous successful crossovers with the franchise.
    """

    result = process_article(
        title=sample_title,
        content=sample_content,
        source_name="Reddit r/Warzone",
        game_name="Call of Duty: Warzone",
    )

    if result:
        logger.info("\n[3/3] Results:")
        logger.info("-" * 70)
        logger.info(f"Original Title: {sample_title}")
        logger.info(f"Cleaned Title: {result['title']}")
        logger.info(f"\nSummary: {result['summary']}")
        logger.info(f"\nBody:\n{result['body']}")
        logger.info(f"\nContent Type: {result['content_type']}")
        logger.info(f"Relevance Score: {result['relevance_score']}")
    else:
        logger.error("Failed to process article")
        return

    # Show cost tracking
    logger.info("\n" + "=" * 70)
    logger.info("Cost Summary:")
    logger.info("=" * 70)
    summary = get_cost_summary()
    logger.info(f"Requests: {summary['request_count']}")
    logger.info(f"Input Tokens: {summary['input_tokens']}")
    logger.info(f"Output Tokens: {summary['output_tokens']}")
    logger.info(f"Total Tokens: {summary['total_tokens']}")
    logger.info(f"Total Cost: ${summary['total_cost_usd']}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
