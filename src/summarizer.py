"""
AI-powered article summarization module.

Uses Anthropic Claude API to generate concise summaries
of news articles (3-5 bullet points, 200-300 characters).
"""

import re
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


# USD per million tokens, matched by substring against the model id.
# Order matters: the first matching prefix wins.
MODEL_PRICING = (
    ('haiku', (1.0, 5.0)),
    ('sonnet', (3.0, 15.0)),
    ('opus', (15.0, 75.0)),
)
DEFAULT_PRICING = (3.0, 15.0)


def _pricing_for(model: str) -> tuple:
    """Input/output price per million tokens for a model id."""
    for needle, prices in MODEL_PRICING:
        if needle in (model or '').lower():
            return prices
    return DEFAULT_PRICING


class CostTracker:
    """
    Track API usage costs per model.

    Since stages run on different models (cheap ones for summaries/scoring,
    the strong one for digest composition), usage is attributed per model id
    and priced with that model's rate.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0
        # model id -> [input_tokens, output_tokens, requests]
        self.per_model: Dict[str, List[int]] = {}

    def add_usage(self, input_tokens: int, output_tokens: int, model: str = None):
        """Record token usage from a request."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_requests += 1

        key = model or Config.CLAUDE_MODEL
        bucket = self.per_model.setdefault(key, [0, 0, 0])
        bucket[0] += input_tokens
        bucket[1] += output_tokens
        bucket[2] += 1

    def get_cost_estimate(self) -> Dict[str, float]:
        """Calculate estimated cost in USD, priced per model."""
        input_cost = 0.0
        output_cost = 0.0
        by_model = {}

        for model, (inp, out, reqs) in self.per_model.items():
            in_price, out_price = _pricing_for(model)
            model_in = (inp / 1_000_000) * in_price
            model_out = (out / 1_000_000) * out_price
            input_cost += model_in
            output_cost += model_out
            by_model[model] = {
                'input_tokens': inp,
                'output_tokens': out,
                'requests': reqs,
                'cost': round(model_in + model_out, 4),
            }

        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'input_cost': round(input_cost, 4),
            'output_cost': round(output_cost, 4),
            'total_cost': round(input_cost + output_cost, 4),
            'requests': self.total_requests,
            'by_model': by_model,
        }

    def __str__(self):
        stats = self.get_cost_estimate()
        parts = [
            f"API Usage: {stats['requests']} requests, "
            f"{stats['input_tokens']} input tokens, "
            f"{stats['output_tokens']} output tokens, "
            f"${stats['total_cost']:.4f} total"
        ]
        for model, data in sorted(stats['by_model'].items()):
            parts.append(
                f"  {model}: {data['requests']} req, ${data['cost']:.4f}"
            )
        return '\n'.join(parts)


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
            model=Config.MODEL_SUMMARIZE,
            max_tokens=50,
            thinking={"type": "disabled"},
            messages=[
                {"role": "user", "content": "Say 'Connection successful' and nothing else."}
            ]
        )

        cost_tracker.add_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=Config.MODEL_SUMMARIZE,
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
                model=Config.MODEL_SUMMARIZE,
                max_tokens=max_tokens,
                # short article summaries: no thinking needed
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}]
            )

            cost_tracker.add_usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=Config.MODEL_SUMMARIZE,
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


EXTRACT_PROMPT = """Summarize this mobile gaming news article AND extract its facts.

Title: {title}

Content:
{content}

Reply with ONLY a JSON object, no other text:
{{
  "summary": "3-5 bullet points using the dot character, 200-300 characters total, for busy mobile gamers",
  "games": ["game titles mentioned, [] if none"],
  "companies": ["studios/publishers/platform holders, [] if none"],
  "platforms": ["iOS", "Android", "Switch", ... , [] if unclear"],
  "event_type": "one of: launch, update, announcement, beta, event, collab, shutdown, deal, warning, business, other",
  "release_date": "YYYY-MM-DD or a vague form like '2026 Q4' if stated, null otherwise",
  "price": "price with currency if stated, null otherwise"
}}"""

ENTITY_FIELDS = ('games', 'companies', 'platforms', 'event_type', 'release_date', 'price')


def _parse_extraction(text: str) -> Optional[dict]:
    """Pull the JSON object out of a model reply; None if unparseable."""
    import json

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def summarize_and_extract(
    title: str,
    content: str,
    max_tokens: int = 700,
    max_retries: int = 3,
) -> tuple:
    """
    Generate a summary AND structured entities in a single API call.

    Extraction rides along with the summary the pipeline already pays for, so
    the marginal cost is a few dozen output tokens rather than a second request.

    Returns:
        (summary: str, entities: dict) — entities is {} when extraction fails.
        Falls back to a plain summary (entities {}) rather than raising, so a
        malformed JSON reply never costs us the summary.
    """
    client = get_client()
    prompt = EXTRACT_PROMPT.format(title=title, content=content[:2000])

    for attempt in range(max_retries):
        try:
            if attempt > 0 or cost_tracker.total_requests > 0:
                time.sleep(Config.API_RATE_LIMIT_SECONDS)

            logger.info(f"Summarizing + extracting: {title[:50]}...")

            response = client.messages.create(
                model=Config.MODEL_EXTRACT,
                max_tokens=max_tokens,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            cost_tracker.add_usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=Config.MODEL_EXTRACT,
            )

            text = next(b.text for b in response.content if b.type == "text")
            data = _parse_extraction(text)

            if not data or not data.get('summary'):
                logger.warning(
                    f"Extraction unparseable for {title[:40]} — falling back to summary only"
                )
                return summarize_article(title, content), {}

            summary = str(data['summary']).strip()
            entities = {k: data[k] for k in ENTITY_FIELDS if data.get(k)}
            return summary, entities

        except RateLimitError as e:
            wait_time = Config.API_RATE_LIMIT_SECONDS * (2 ** attempt)
            logger.warning(
                f"Rate limited, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(wait_time)
            if attempt == max_retries - 1:
                raise SummarizationError(
                    f"API rate limit exceeded after {max_retries} retries: {e}"
                )

        except APIConnectionError as e:
            raise SummarizationError(f"Failed to connect to Anthropic API: {e}")
        except APIError as e:
            raise SummarizationError(f"Anthropic API error: {e}")


def summarize_batch(
    articles: List[dict],
    db_path: str = None,
    extract_entities: bool = True,
) -> Dict[str, any]:
    """
    Summarize multiple articles with rate limiting.

    Args:
        articles: List of article dicts (must have 'url', 'title', 'content')
        db_path: If provided, save summaries to DB after each one
        extract_entities: Also pull structured facts in the same API call

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
            if extract_entities:
                summary, entities = summarize_and_extract(title, content)
            else:
                summary, entities = summarize_article(title, content), {}

            if db_path and url:
                update_article_summary(url, summary, db_path, entities=entities)
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
