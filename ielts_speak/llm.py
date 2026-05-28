"""LLM API client (OpenAI-compatible)."""

from openai import OpenAI

from . import config
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


class LLMError(Exception):
    """Raised when the API call fails."""
    pass


_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.API_KEY:
            raise LLMError(
                "API key not set. Export IELTS_API_KEY or OPENAI_API_KEY,\n"
                "or create a .env file in the project root with:\n"
                "  IELTS_API_KEY=sk-your-key-here\n"
                "  IELTS_API_BASE=https://api.openai.com/v1  # optional"
            )
        _client = OpenAI(api_key=config.API_KEY, base_url=config.API_BASE)
    return _client


def generate(word: str) -> str:
    """Call the LLM and return the generated response text."""
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(word=word)},
            ],
        )
        return response.choices[0].message.content

    except Exception as e:
        raise LLMError(f"API call failed: {e}") from e
