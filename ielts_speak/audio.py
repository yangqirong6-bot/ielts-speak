"""TTS generation and STT recording for IELTS speaking practice."""

import asyncio
import re
from pathlib import Path


# ── Text extraction ─────────────────────────────────────────────────

def extract_sample_text(content: str) -> dict[str, str]:
    """Extract Part 2 and Part 3 English sample answers from LLM output."""
    result = {"part2": "", "part3": ""}

    m = re.search(r"\*\*Sample:\*\*\s*(.+?)(?=\n\n|\n###|\n\*\*|\Z)", content, re.DOTALL)
    if m:
        result["part2"] = m.group(1).strip()

    m = re.search(r"\*\*A:\*\*\s*(.+?)(?=\n\n|\n###|\n\*\*|\Z)", content, re.DOTALL)
    if m:
        result["part3"] = m.group(1).strip()

    return result


def get_practice_text(content: str) -> str:
    """Combine Part 2 + Part 3 English samples for reading-aloud practice."""
    samples = extract_sample_text(content)
    parts = [samples["part2"], samples["part3"]]
    return " ".join(p for p in parts if p)


# ── TTS (edge-tts) ──────────────────────────────────────────────────

def _clean_for_tts(text: str) -> str:
    """Strip Markdown syntax and filler words before TTS synthesis.

    Removes **, *, #, backticks, and the word 'asterisk' so the TTS
    engine reads only clean spoken English.
    """
    # Remove Markdown heading markers
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Remove bold markers: **text** → text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove italic markers: *text* → text (but not the * in asterisk)
    text = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", text)
    # Remove inline code backticks
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
    # Remove links: [text](url) → text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Remove image syntax: ![alt](url)
    text = re.sub(r"!\[.*?\]\(.+?\)", "", text)
    # Remove the word "asterisk" (common TTS hallucination trigger)
    text = re.sub(r"\basterisk\b", "", text, flags=re.IGNORECASE)
    # Remove horizontal rules
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Remove remaining stray * characters
    text = text.replace("*", "")
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


async def _tts_to_file(text: str, output_path: Path, voice: str = "en-GB-SoniaNeural"):
    """Async: generate TTS audio via Microsoft Edge TTS and save as MP3."""
    import edge_tts

    clean = _clean_for_tts(text)
    communicate = edge_tts.Communicate(clean, voice)
    await communicate.save(str(output_path))


def generate_tts_for_word(word: str, content: str, output_dir: Path) -> Path | None:
    """Generate MP3 audio for the word's English sample answers. Returns path or None."""
    samples = extract_sample_text(content)
    parts = [samples["part2"], samples["part3"]]
    text = " ".join(p for p in parts if p)

    if not text:
        return None

    safe_word = word.strip().replace(" ", "_").replace("/", "_")
    mp3_path = output_dir / f"{safe_word}_sample.mp3"

    try:
        asyncio.run(_tts_to_file(text, mp3_path))
        return mp3_path
    except ImportError:
        raise RuntimeError("edge-tts is not installed. Run: pip install edge-tts")
    except Exception as e:
        raise RuntimeError(f"TTS generation failed: {e}") from e


# ── Per-block dialogue extraction + TTS ──────────────────────────────

_DIALOGUE_MARKER_RE = re.compile(
    r"\*\*(?:Q|A|Sample):\*\*\s*(.+?)(?=\n\*\*|\n###|\Z)",
    re.DOTALL,
)


def extract_dialogue_lines(block_text: str) -> str:
    """Extract English Q:/A:/Sample: dialogue from a content block.

    Step 1 — regex with DOTALL: match **Q:** / **A:** / **Sample:** and
    capture the English text that follows (can span multiple lines).

    Step 2 — fallback (if regex finds nothing): strip all CJK characters
    and Markdown symbols, keep remaining English text.

    Returns clean spoken English ready for TTS, or empty string.
    """
    # ── Step 1: structured extraction ──────────────────────────────
    matches = _DIALOGUE_MARKER_RE.findall(block_text)
    if matches:
        parts = [m.strip() for m in matches if m.strip()]
        if parts:
            return " ".join(parts)

    # ── Step 2: fallback — brute-force Chinese removal ────────────
    fallback = block_text
    # Remove CJK + fullwidth punctuation
    fallback = re.sub(r"[一-鿿　-〿＀-￯]+", " ", fallback)
    # Remove Markdown headers / markers **text**, #, *, etc.
    fallback = re.sub(r"\*\*[^*]+\*\*", " ", fallback)
    fallback = re.sub(r"[*#_\[\]()`>|]", " ", fallback)
    # Remove standalone short labels like "Q", "A", "Sample"
    fallback = re.sub(r"\b(Cue Card Topic|Topic|Theme|Sample|Q|A)\b", " ", fallback)
    # Collapse whitespace
    fallback = re.sub(r"\s+", " ", fallback).strip()
    return fallback


def generate_dialogue_tts(block_text: str, output_path: Path) -> Path | None:
    """Extract English dialogue from a block and generate TTS audio.

    Returns path to MP3 file, or None if no dialogue was found.
    """
    dialogue = extract_dialogue_lines(block_text)
    if not dialogue:
        return None

    try:
        asyncio.run(_tts_to_file(dialogue, output_path))
        return output_path
    except ImportError:
        raise RuntimeError("edge-tts is not installed. Run: pip install edge-tts")
    except Exception as e:
        raise RuntimeError(f"TTS generation failed: {e}") from e


# ── STT (SpeechRecognition) ─────────────────────────────────────────

def clean_transcription(text: str) -> str:
    """Remove common STT hallucination words and normalize whitespace."""
    words_to_remove = ["asterisk", "hash", "underscore"]
    for word in words_to_remove:
        text = re.sub(rf"\b{word}\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def record_and_transcribe(timeout: int = 8, phrase_limit: int = 35) -> str:
    """Record from microphone and transcribe via Google STT. Returns transcribed text."""
    try:
        import speech_recognition as sr
    except ImportError:
        raise RuntimeError(
            "SpeechRecognition is not installed. Run: pip install SpeechRecognition"
        )

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
    except OSError as e:
        raise RuntimeError(
            f"Microphone not available: {e}\n"
            "On Windows, you may need to install pyaudio: pip install pyaudio"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Recording failed: {e}") from e

    try:
        return clean_transcription(recognizer.recognize_google(audio))
    except sr.UnknownValueError:
        raise RuntimeError(
            "Could not understand the audio. Please try again, speak clearly and closer to the microphone."
        )
    except sr.RequestError as e:
        raise RuntimeError(f"Google STT service error: {e}") from e
