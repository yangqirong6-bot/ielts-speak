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


def generate(word: str, user_thought: str = "") -> str:
    """Call the LLM and return the generated response text."""
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                    word=word,
                    user_thought=user_thought or "（学生未提供具体思路，请根据词汇通用场景自由发挥）",
                )},
            ],
        )
    except Exception as e:
        detail = str(e)
        if hasattr(e, "status_code"):
            detail = f"HTTP {e.status_code} — {detail}"
        if hasattr(e, "response"):
            try:
                body = e.response.json()
                detail = f"{detail}\nResponse body: {body}"
            except Exception:
                detail = f"{detail}\nResponse text: {e.response.text[:500]}"
        raise LLMError(f"API call failed: {detail}") from e

    content = response.choices[0].message.content
    if not content:
        finish = response.choices[0].finish_reason
        raise LLMError(
            f"API returned empty content (finish_reason={finish}). "
            f"Model: {config.MODEL}. The model may have refused to answer."
        )

    return content


def review_pronunciation(original: str, transcribed: str) -> str:
    """Send original + transcribed text to LLM for pronunciation feedback."""
    from .prompts import PRONUNCIATION_REVIEW_TEMPLATE

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            temperature=0.5,
            max_tokens=500,
            messages=[
                {"role": "user", "content": PRONUNCIATION_REVIEW_TEMPLATE.format(
                    original=original,
                    transcribed=transcribed,
                )},
            ],
        )
    except Exception as e:
        detail = str(e)
        if hasattr(e, "status_code"):
            detail = f"HTTP {e.status_code} — {detail}"
        raise LLMError(f"Pronunciation review failed: {detail}") from e

    content = response.choices[0].message.content
    if not content:
        raise LLMError("No pronunciation feedback received.")
    return content
