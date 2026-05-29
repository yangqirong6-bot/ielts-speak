"""Configuration from environment variables."""

import os
from pathlib import Path


def _load_dotenv():
    """Load .env file if python-dotenv is available, silently skip if not."""
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass


_load_dotenv()

# LLM API settings
API_KEY = os.getenv("IELTS_API_KEY", os.getenv("OPENAI_API_KEY", ""))
API_BASE = os.getenv("IELTS_API_BASE", os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"))
MODEL = os.getenv("IELTS_MODEL", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("IELTS_TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("IELTS_MAX_TOKENS", "2048"))

# Output settings
OUTPUT_DIR = Path(os.getenv("IELTS_OUTPUT_DIR", str(Path(__file__).parent.parent / "output")))
