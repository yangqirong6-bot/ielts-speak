"""Save generated content to local .md files."""

from datetime import datetime
from pathlib import Path

from . import config


def save(word: str, content: str) -> Path:
    """Save generated IELTS material to a markdown file.

    Returns the path to the saved file.
    """
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_word = word.strip().replace(" ", "_").replace("/", "_")
    filename = f"{safe_word}_{timestamp}.md"
    filepath = config.OUTPUT_DIR / filename

    header = "---\n"
    header += f"word: {word}\n"
    header += f"date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    header += f"model: {config.MODEL}\n"
    header += "---\n\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(content)

    return filepath


def list_saved() -> list[Path]:
    """List all saved .md files, most recent first."""
    if not config.OUTPUT_DIR.exists():
        return []
    files = sorted(config.OUTPUT_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files
