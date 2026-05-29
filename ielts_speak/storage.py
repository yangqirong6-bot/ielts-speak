"""Save generated content to interlinked Obsidian .md files."""

import re
from datetime import datetime
from pathlib import Path

from . import config


def save(word: str, content: str) -> Path:
    """Save generated IELTS material to the main markdown file.

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


# ── Linked Notes parsing ────────────────────────────────────────────

_WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")

_CATEGORY_HEADERS = {
    "synonyms": "synonyms",
    "antonyms": "antonyms",
    "collocations": "collocations",
    "ielts topics": "topics",
    "ielts topic": "topics",
}


def _parse_linked_notes(content: str) -> dict[str, list[tuple[str, str]]]:
    """Parse the ### Linked Notes section into structured data.

    Returns dict with keys: synonyms, antonyms, collocations, topics.
    Each value is a list of (name, note) tuples.
    """
    result: dict[str, list[tuple[str, str]]] = {
        "synonyms": [],
        "antonyms": [],
        "collocations": [],
        "topics": [],
    }

    # Find the Linked Notes section
    marker = "### Linked Notes"
    idx = content.find(marker)
    if idx == -1:
        marker_lower = "### linked notes"
        idx = content.find(marker_lower)
    if idx == -1:
        return result

    section_text = content[idx + len(marker):]

    # Split into categories by looking for **Category:** patterns
    # Find all **...** headers and their positions
    current_category: str | None = None
    current_body: list[str] = []

    for line in section_text.splitlines():
        stripped = line.strip()

        # Check if this line is a category header: **Something:**
        if stripped.startswith("**") and "**" in stripped[2:]:
            # Save previous category
            if current_category and current_body:
                key = _CATEGORY_HEADERS.get(current_category.lower())
                if key:
                    _extract_links(current_body, key, result)
            # Start new category
            header_end = stripped.find("**", 2)
            if header_end != -1:
                current_category = stripped[2:header_end].rstrip(":").strip()
            current_body = []
        elif current_category and stripped:
            current_body.append(stripped)

    # Don't forget the last category
    if current_category and current_body:
        key = _CATEGORY_HEADERS.get(current_category.lower())
        if key:
            _extract_links(current_body, key, result)

    return result


def _extract_links(
    lines: list[str],
    key: str,
    result: dict[str, list[tuple[str, str]]],
) -> None:
    """Extract [[wikilinks]] and trailing notes from a list of bullet lines."""
    for line in lines:
        # Strip leading bullet: "- ", "* ", or just "-"
        line = line.lstrip("-*").strip()
        wm = _WIKILINK_RE.search(line)
        if not wm:
            continue
        name = wm.group(1).strip()
        note = line[wm.end():].strip().lstrip("—").lstrip("-").strip()
        result[key].append((name, note))


# ── Sub-note writers ────────────────────────────────────────────────

def _ensure_subdir(name: str) -> Path:
    d = config.OUTPUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(name: str) -> str:
    return name.strip().replace(" ", "-").replace("/", "-").replace("\\", "-")


def _write_subnote(dir_name: str, name: str, parent_word: str,
                   note_type: str, extra_frontmatter: str = "",
                   body_lines: list[str] | None = None) -> Path:
    """Write a single sub-note and return its path."""
    d = _ensure_subdir(dir_name)
    safe = _safe_filename(name)
    filepath = d / f"{safe}.md"

    fm = "---\n"
    fm += f"type: {note_type}\n"
    fm += f"parent: \"[[{parent_word}]]\"\n"
    if extra_frontmatter:
        fm += extra_frontmatter
    fm += "---\n\n"
    fm += f"# {name}\n\n"
    fm += f"**Parent:** [[{parent_word}]]\n\n"
    if body_lines:
        fm += "\n".join(body_lines) + "\n"

    # Topic notes: append to existing rather than overwrite
    if note_type == "topic" and filepath.exists():
        existing = filepath.read_text(encoding="utf-8")
        link_line = f"- [[{parent_word}]]"
        if link_line not in existing:
            # Insert after the ## Words section or append
            if "## Words" in existing:
                existing = existing.rstrip() + f"\n{link_line}\n"
            else:
                existing += f"\n## Words\n\n{link_line}\n"
            filepath.write_text(existing, encoding="utf-8")
        return filepath

    filepath.write_text(fm, encoding="utf-8")
    return filepath


def save_interlinked(word: str, content: str) -> list[Path]:
    """Save main note AND all linked sub-notes for Obsidian graph view.

    Returns a list of all created/updated file paths.
    """
    saved: list[Path] = []

    # 1. Main note
    main_path = save(word, content)
    saved.append(main_path)

    # 2. Parse linked notes
    linked = _parse_linked_notes(content)

    # 3. Synonyms
    for name, note in linked["synonyms"]:
        body = [f"**Context difference:** {note}"] if note else []
        p = _write_subnote("synonyms", name, word, "synonym", body_lines=body)
        saved.append(p)

    # 4. Antonyms
    for name, note in linked["antonyms"]:
        body = [f"**Meaning:** {note}"] if note else []
        p = _write_subnote("antonyms", name, word, "antonym", body_lines=body)
        saved.append(p)

    # 5. Collocations
    for name, note in linked["collocations"]:
        body = [f"**Usage note:** {note}"] if note else []
        p = _write_subnote("collocations", name, word, "collocation", body_lines=body)
        saved.append(p)

    # 6. Topics (append mode — accumulates words per topic)
    for name, note in linked["topics"]:
        body = [f"**Context:** {note}"] if note else []
        p = _write_subnote("topics", name, word, "topic", body_lines=body)
        saved.append(p)

    return saved


def list_saved() -> list[Path]:
    """List all saved main .md files, most recent first."""
    if not config.OUTPUT_DIR.exists():
        return []
    files = sorted(
        config.OUTPUT_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files
