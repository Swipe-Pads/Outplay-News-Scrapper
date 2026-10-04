"""
Gemini on Google Cloud Vertex AI behind the Anthropic-style client interface.

The pipeline calls ``client.messages.create(model=..., max_tokens=..., messages=[...])``
in several places and reads ``response.content`` / ``response.usage``. This adapter
answers those calls with Gemini so the call sites stay unchanged. The ``model``
argument (a Claude model name) is ignored; ``Config.GEMINI_MODEL`` is used instead.

Why Gemini: Google for Startups credits cover first-party Vertex AI models
(Gemini), not partner models such as Claude.
"""

import os
import time
import logging
from types import SimpleNamespace

from google import genai
from google.genai import types, errors

from src.config import Config
from src.summarizer import SummarizationError

logger = logging.getLogger(__name__)

# Gemini counts thinking tokens against max_output_tokens, so headroom is added on top of
# the caller's max_tokens. Gemini 2.x honours thinking_budget=0; Gemini 3.x ignores it and
# thinks anyway (observed: summaries cut off at MAX_TOKENS), so 3.x gets a thinking level.
_THINKING_BUDGET = 2048          # 2.x, calls that keep thinking on (digest composition)
_HEADROOM_LOW = 4096             # 3.x, thinking_level=low  (~0.7-0.9k thought tokens observed)
_HEADROOM_HIGH = 16384           # 3.x, thinking_level=high (digest composition)
_MAX_ATTEMPTS = 4
_RETRYABLE_CODES = {429, 500, 502, 503, 504}


class AIBackendError(SummarizationError):
    """Gemini call failed after retries (or with a non-retryable error)."""
    pass


class _Messages:
    def __init__(self, client: genai.Client):
        self._client = client

    def create(self, *, model=None, max_tokens, messages, system=None, thinking=None, **_ignored):
        thinking_off = isinstance(thinking, dict) and thinking.get('type') == 'disabled'
        if Config.GEMINI_MODEL.startswith('gemini-2'):
            budget = 0 if thinking_off else _THINKING_BUDGET
            thinking_config = types.ThinkingConfig(thinking_budget=budget)
            headroom = budget
        else:
            thinking_config = types.ThinkingConfig(thinking_level='low' if thinking_off else 'high')
            headroom = _HEADROOM_LOW if thinking_off else _HEADROOM_HIGH
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens + headroom,
            thinking_config=thinking_config,
            system_instruction=system,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents = [
            types.Content(
                role='model' if m['role'] == 'assistant' else 'user',
                parts=[types.Part.from_text(text=m['content'])],
            )
            for m in messages
        ]

        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.models.generate_content(
                    model=Config.GEMINI_MODEL, contents=contents, config=config
                )
                break
            except errors.APIError as e:
                if e.code in _RETRYABLE_CODES and attempt < _MAX_ATTEMPTS - 1:
                    wait = Config.API_RATE_LIMIT_SECONDS * (2 ** (attempt + 1))
                    logger.warning(f"Gemini error {e.code}, retrying in {wait}s (attempt {attempt + 1}/{_MAX_ATTEMPTS})")
                    time.sleep(wait)
                    continue
                raise AIBackendError(f"Gemini API error {e.code}: {e.message}") from e

        usage = response.usage_metadata
        candidate = response.candidates[0] if response.candidates else None
        return SimpleNamespace(
            model=Config.GEMINI_MODEL,
            content=[SimpleNamespace(type='text', text=response.text or '')],
            stop_reason=str(candidate.finish_reason) if candidate else None,
            usage=SimpleNamespace(
                input_tokens=(usage.prompt_token_count or 0) if usage else 0,
                output_tokens=((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0,
            ),
        )


class GeminiVertexClient:
    """Minimal stand-in for ``anthropic.Anthropic`` exposing ``.messages.create``."""

    def __init__(self, project_id: str, region: str):
        # GitHub Actions authenticates via ADC (google-github-actions/auth). For a local
        # one-off run, VERTEX_ACCESS_TOKEN (e.g. `gcloud auth print-access-token`) can be used instead.
        credentials = None
        if os.getenv('VERTEX_ACCESS_TOKEN'):
            from google.oauth2.credentials import Credentials
            credentials = Credentials(os.environ['VERTEX_ACCESS_TOKEN'].strip())
        self.messages = _Messages(
            genai.Client(vertexai=True, project=project_id, location=region, credentials=credentials)
        )
