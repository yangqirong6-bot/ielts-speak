#!/usr/bin/env python3
"""Streamlit web UI for IELTS Speaking Vocabulary Coach.

Usage: streamlit run app.py
"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import streamlit.components.v1 as components
import re
import markdown
from bs4 import BeautifulSoup

from ielts_speak import config as cfg
from ielts_speak import llm as llm_module
from ielts_speak.llm import generate, review_pronunciation, LLMError
from ielts_speak.storage import save_interlinked, list_saved
from ielts_speak.audio import (
    generate_dialogue_tts,
    extract_dialogue_lines,
    get_practice_text,
    clean_transcription,
)

st.set_page_config(
    page_title="IELTS Speaking Coach",
    page_icon="🎓",
    layout="centered",
)

# ── Global typography (dark-mode optimised) ──────────────────────────

st.markdown("""
<style>
  /* Body text */
  .block-container p, .block-container li, .block-container td, .block-container th {
    font-size: 17px;
    line-height: 1.7;
    color: #E0E0E0;
  }
  .block-container h2 { margin-top: 2.5rem; margin-bottom: 1rem; }
  .block-container h3 { margin-top: 2rem; margin-bottom: 0.75rem; }
  .block-container strong { color: #F0F2F6; }
  .block-container code { color: #c4b5fd; }

  /* Click-to-dictionary word — subtle highlight on hover */
  .clickable-word {
    cursor: pointer;
    transition: background-color 0.2s;
  }
  .clickable-word:hover {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
  }

  /* Dictionary tooltip card (created by radar iframe) */
  .dict-tooltip {
    position: fixed; z-index: 2147483647;
    background: #1e1e30; border: 1px solid #374151;
    border-radius: 10px; box-shadow: 0 8px 32px rgba(0,0,0,.55);
    padding: 14px 18px; max-width: 320px; min-width: 200px;
    font-family: "Source Sans Pro", sans-serif;
  }
  .dict-tooltip .dw { font-size: 18px; font-weight: 700; color: #a5b4fc; margin-bottom: 2px; }
  .dict-tooltip .dp { font-size: 13px; color: #9ca3af; margin-bottom: 4px; }
  .dict-tooltip .dpos { font-size: 12px; font-style: italic; color: #9ca3af; margin-bottom: 6px; }
  .dict-tooltip .dzh { font-size: 15px; font-weight: 700; color: #00b894; margin-bottom: 6px; }
  .dict-tooltip .ddef { font-size: 14px; line-height: 1.5; color: #E0E0E0; margin-bottom: 4px; }
  .dict-tooltip .derr { font-size: 14px; color: #ef4444; }
  .dict-tooltip .dexa { font-size: 13px; color: #9ca3af; font-style: italic; }
  .dict-tooltip .loading { font-size: 14px; color: #9ca3af; }
</style>
""", unsafe_allow_html=True)

# ── Session init ─────────────────────────────────────────────────────

for key, default in [
    ("content", ""),
    ("word", ""),
    ("content_ready", False),
    ("block_audio", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar: API Config ──────────────────────────────────────────────

with st.sidebar:
    st.header("API Configuration")

    api_key = st.text_input(
        "API Key",
        value=cfg.API_KEY or "",
        type="password",
        help="Your OpenAI-compatible API key",
    )
    api_base = st.text_input(
        "API Base URL",
        value=cfg.API_BASE or "",
        help="e.g. https://api.deepseek.com/v1",
    )
    model_name = st.text_input(
        "Model",
        value=cfg.MODEL or "",
        help="e.g. deepseek-v4-flash, gpt-4o-mini",
    )

    if st.button("Apply Config", use_container_width=True):
        changed = (
            api_key != cfg.API_KEY
            or api_base != cfg.API_BASE
            or model_name != cfg.MODEL
        )
        cfg.API_KEY = api_key
        cfg.API_BASE = api_base
        cfg.MODEL = model_name
        if changed:
            llm_module._client = None
        st.success("Config applied!")

    st.divider()

    st.header("Saved Files")
    files = list_saved()
    if files:
        for f in files[:20]:
            st.caption(f"• {f.name}")
    else:
        st.caption("No files yet")

# ── Main UI ──────────────────────────────────────────────────────────

st.title("IELTS Speaking Vocabulary Coach")
st.caption(
    "雅思口语词汇陪练 — 输入单词，获取 Part 1/2/3 场景 + 地道搭配"
)

col1, col2 = st.columns(2)
with col1:
    word = st.text_input("Target Word", placeholder="e.g. ambitious")
with col2:
    user_thought = st.text_input(
        "Your Context (optional)",
        placeholder="Part 2/3 你打算结合什么经历展开？",
    )

can_generate = bool(word.strip() and cfg.API_KEY)

if st.button(
    "Generate", type="primary", use_container_width=True,
    disabled=not can_generate,
):
    with st.spinner(f"Generating IELTS material for '{word.strip()}'..."):
        try:
            content = generate(word.strip(), user_thought.strip())
        except LLMError as e:
            st.error(str(e))
            st.stop()

    st.session_state.content = content
    st.session_state.word = word.strip()
    st.session_state.content_ready = True
    st.session_state.block_audio = {}
    st.rerun()

# ── Mermaid rendering ─────────────────────────────────────────────────

_MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

_MERMAID_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body { margin: 0; padding: 12px; background: transparent; }
  .mermaid { display: flex; justify-content: center; }
</style>
</head>
<body>
<div class="mermaid">
{code}
</div>
<script>mermaid.initialize({ startOnLoad: true, theme: 'dark' });</script>
</body>
</html>"""


def _render_mermaid(code: str, height: int = 520) -> None:
    html = _MERMAID_HTML.replace("{code}", code)
    components.html(html, height=height, scrolling=True)


# ── Hidden radar: click listener + dictionary tooltip only (no DOM mutation) ──

_RADAR_HTML = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body>
<script>
(function() {
  var pdoc = window.parent.document;
  var pwin = window.parent;
  var tooltip = null;

  function hideTT() {
    if (tooltip) { tooltip.remove(); tooltip = null; }
  }

  function position(div, x, y) {
    div.style.left = Math.min(x - 10, pwin.innerWidth - 340) + 'px';
    div.style.top = Math.max(10, y + 16) + 'px';
  }

  function showLoading(word, x, y) {
    hideTT();
    var div = pdoc.createElement('div');
    div.className = 'dict-tooltip';
    div.innerHTML = '<div class="dw">' + word + '</div><div class="loading">Looking up...</div>';
    position(div, x, y);
    pdoc.body.appendChild(div);
    tooltip = div;
  }

  function showResult(word, dictData, zhText, x, y) {
    hideTT();
    var div = pdoc.createElement('div');
    div.className = 'dict-tooltip';

    var h = '<div class="dw">' + word + '</div>';

    var entry = null, meaning = null, ph = '';
    if (dictData && dictData.length) {
      entry = dictData[0];
      if (entry.phonetics) {
        for (var i = 0; i < entry.phonetics.length; i++)
          if (entry.phonetics[i].text) { ph = entry.phonetics[i].text; break; }
      }
      if (!ph && entry.phonetic) ph = entry.phonetic;
      meaning = entry.meanings && entry.meanings[0];
    }

    if (ph) h += '<div class="dp">/' + ph + '/</div>';

    // Chinese translation (Google Translate — shown prominently)
    if (zhText) h += '<div class="dzh">' + zhText + '</div>';

    // English definition (from dictionary API)
    if (meaning) {
      h += '<div class="dpos">' + meaning.partOfSpeech + '</div>';
      var def = meaning.definitions && meaning.definitions[0];
      if (def) h += '<div class="ddef">' + def.definition + '</div>';
      if (def && def.example) h += '<div class="dexa">&quot;' + def.example + '&quot;</div>';
    }

    div.innerHTML = h;
    position(div, x, y);
    pdoc.body.appendChild(div);
    tooltip = div;
  }

  function showError(msg, x, y) {
    hideTT();
    var div = pdoc.createElement('div');
    div.className = 'dict-tooltip';
    div.innerHTML = '<div class="derr">' + msg + '</div>';
    position(div, x, y);
    pdoc.body.appendChild(div);
    tooltip = div;
  }

  pdoc.body.addEventListener('click', async function(e) {
    if (tooltip && tooltip.contains(e.target)) return;
    var span = e.target.closest('.clickable-word');
    if (span) {
      var word = span.textContent.trim();
      if (!word || word.length < 2 || word.length > 40) return;
      showLoading(word, e.clientX, e.clientY);

      try {
        var results = await Promise.all([
          fetch('https://api.dictionaryapi.dev/api/v2/entries/en/' + encodeURIComponent(word))
            .then(function(r) { return r.ok ? r.json() : null; })
            .catch(function() { return null; }),
          fetch('https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=' + encodeURIComponent(word))
            .then(function(r) { return r.json(); })
            .then(function(d) { return (d && d[0] && d[0][0]) ? d[0][0][0] : ''; })
            .catch(function() { return ''; })
        ]);

        var dictData = results[0];
        var zhText = results[1];

        if (!dictData && !zhText) {
          showError('No definition found', e.clientX, e.clientY);
          return;
        }
        showResult(word, dictData, zhText, e.clientX, e.clientY);
      } catch(err) {
        showError('Lookup failed', e.clientX, e.clientY);
      }
      return;
    }
    hideTT();
  });

  pdoc.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') hideTT();
  });
})();
</script>
</body></html>"""


def _render_radar() -> None:
    components.html(_RADAR_HTML, height=0)


# ── Python-side word wrapping (no JS DOM mutation → no React crash) ─────

_SKIP_TAGS = {"code", "pre", "script", "style"}


def _process_text_for_translation(text: str) -> str:
    """Convert markdown → HTML, wrap every English word in .clickable-word.

    Uses nl2br to preserve line-breaks, then re.sub on ALL text nodes
    (including inside <strong>, <em>, <li>, etc.) so no word is missed.
    """
    html = markdown.markdown(
        text, extensions=["nl2br", "fenced_code", "sane_lists"],
    )
    soup = BeautifulSoup(html, "html.parser")

    for text_node in soup.find_all(string=True):
        if text_node.parent.name in _SKIP_TAGS:
            continue

        original_text = str(text_node)
        if not re.search(r"[a-zA-Z]{2,}", original_text):
            continue

        new_html = re.sub(
            r"\b([a-zA-Z]{2,})\b",
            r'<span class="clickable-word">\1</span>',
            original_text,
        )
        new_soup = BeautifulSoup(new_html, "html.parser")
        text_node.replace_with(new_soup)

    return str(soup)


# ── Mermaid sanitisation ────────────────────────────────────────────────

def _clean_mermaid(code: str) -> str:
    """Light sanitisation: replace smart quotes / unicode that trip Mermaid.

    Brackets () [] {} are PRESERVED — they are essential Mermaid syntax.
    Only characters known to cause parser bombs are cleaned.
    """
    # Smart / curly quotes → straight quote
    code = code.replace("“", '"').replace("”", '"')
    code = code.replace("‘", "'").replace("’", "'")
    # Full-width forms of mermaid operators that LLMs sometimes emit
    code = code.replace("：", ":")   # ：→ :
    code = code.replace("；", ";")   # ；→ ;
    # Zero-width & invisible characters
    code = re.sub(r"[​‌‍‎‏ ]", "", code)
    return code.strip()


# ── Content rendering helpers ─────────────────────────────────────────

_SECTION_SPLIT_RE = re.compile(r"(?=^### )", re.MULTILINE)
_DIALOGUE_PARTS = {"Part 1", "Part 2", "Part 3"}

# (bg, fg) colour pairs for Linked Notes wikilink pills
_WIKILINK_COLORS: dict[str, tuple[str, str]] = {
    "synonyms":     ("#1e3a5f", "#93c5fd"),
    "antonyms":     ("#5f1e3a", "#fca5a5"),
    "collocations": ("#1e5f3a", "#6ee7b7"),
    "topics":       ("#3a1e5f", "#c4b5fd"),
}


def _get_block_heading(block: str) -> str | None:
    m = re.match(r"^### (.+)$", block.strip(), re.MULTILINE)
    return m.group(1).strip() if m else None


def _block_has_dialogue(block: str) -> bool:
    return any(
        re.match(r"\*\*(Q|A|Sample):\*\*", line.strip())
        for line in block.splitlines()
    )


def _beautify_linked_notes(content: str) -> str:
    """Replace [[wikilinks]] with coloured HTML <span> pills (display only)."""
    marker = "### Linked Notes"
    idx = content.find(marker)
    if idx == -1:
        return content

    before = content[:idx]
    section = content[idx:]

    current_category: str | None = None
    result: list[str] = []

    for line in section.splitlines(keepends=True):
        sl = line.strip().lower()
        if sl.startswith("**synonyms"):
            current_category = "synonyms"
        elif sl.startswith("**antonyms"):
            current_category = "antonyms"
        elif sl.startswith("**collocations"):
            current_category = "collocations"
        elif sl.startswith("**ielts topics") or sl.startswith("**ielts topic"):
            current_category = "topics"
        elif sl.startswith("**") and "**" in sl[2:]:
            current_category = None

        if current_category and current_category in _WIKILINK_COLORS:
            bg, fg = _WIKILINK_COLORS[current_category]
            def _pill(m: re.Match) -> str:
                name = m.group(1)
                return (
                    f'<span style="display:inline-block;background:{bg};'
                    f'color:{fg};border-radius:8px;padding:1px 8px;'
                    f'font-weight:600;margin:1px 2px;">{name}</span>'
                )
            line = re.sub(r"\[\[(.+?)\]\]", _pill, line)
        result.append(line)

    return before + "".join(result)


def _render_audio_button(block: str, heading: str) -> None:
    word = st.session_state.word
    label = re.sub(r"\*|\(|\)|（|）", "", heading).strip()
    slug = label.replace(" ", "-").replace("/", "-")

    if label in st.session_state.block_audio:
        path = st.session_state.block_audio[label]
        if Path(path).exists():
            st.audio(path)

    btn_key = f"tts_{slug}_{word}"
    if st.button(f"🔊 Generate {label} Audio", key=btn_key):
        dialogue = extract_dialogue_lines(block)
        if not dialogue:
            st.warning("No English dialogue found in this block.")
            return
        cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_word = word.replace(" ", "_").replace("/", "_")
        mp3_path = cfg.OUTPUT_DIR / f"{safe_word}_{slug}.mp3"
        with st.spinner(f"Generating {label} audio..."):
            try:
                generate_dialogue_tts(block, mp3_path)
                st.session_state.block_audio[label] = str(mp3_path)
            except RuntimeError as e:
                st.error(str(e))


def _render_content(content: str) -> None:
    """Render IELTS blocks in order, with per-block audio buttons inline.

    English words are wrapped in .clickable-word spans in Python (BeautifulSoup),
    so React never sees a DOM mutation — no virtual-DOM mismatch.
    """
    # 1. Extract & remove Mermaid block
    mermaid_code: str | None = None
    mm = _MERMAID_BLOCK_RE.search(content)
    if mm:
        mermaid_code = mm.group(1).strip()
        content = content[:mm.start()] + content[mm.end():]

    # 2. Beautify Linked Notes (coloured wikilink pills)
    content = _beautify_linked_notes(content)

    # 3. Split into sections by ### headers, render in order
    blocks = [b.strip() for b in _SECTION_SPLIT_RE.split(content) if b.strip()]

    for block in blocks:
        heading = _get_block_heading(block)
        is_dialogue = heading and any(p in heading for p in _DIALOGUE_PARTS)

        processed = _process_text_for_translation(block)
        st.markdown(processed, unsafe_allow_html=True)

        if is_dialogue and _block_has_dialogue(block):
            _render_audio_button(block, heading)

    # 4. Render Mermaid diagram (centred via columns)
    if mermaid_code:
        st.caption("🧠 *Vocabulary Mindmap*")
        _, centre, _ = st.columns([1, 4, 1])
        with centre:
            _render_mermaid(_clean_mermaid(mermaid_code))


# ── Content Display ──────────────────────────────────────────────────

if st.session_state.content_ready:
    _render_content(st.session_state.content)

    st.divider()
    st.header("Practice Tools")

    tab1, tab2 = st.tabs(["🎤 Reading Test", "💾 Save"])

    content = st.session_state.content
    word = st.session_state.word

    # ── Tab 1: Reading Test ─────────────────────────────────────────

    with tab1:
        st.caption(
            "Record yourself reading the sample text. "
            "The AI examiner will analyze your pronunciation."
        )

        practice_text = get_practice_text(content)
        if not practice_text:
            st.warning("No English sample text found for reading practice.")
        else:
            st.markdown("**Read this aloud:**")
            st.info(practice_text)

            try:
                from audiorecorder import audiorecorder

                audio = audiorecorder()
            except ImportError:
                st.error(
                    "streamlit-audiorecorder is not installed. "
                    "Run: pip install streamlit-audiorecorder"
                )
                audio = None

            if audio is not None and len(audio) > 0:
                st.audio(audio.export().read())

                if st.button("Submit for Review", type="primary", key="review_btn"):
                    tmp_path = None
                    try:
                        import speech_recognition as sr

                        wav_bytes = audio.export(format="wav").read()
                        with tempfile.NamedTemporaryFile(
                            suffix=".wav", delete=False
                        ) as tmp:
                            tmp.write(wav_bytes)
                            tmp_path = tmp.name

                        recognizer = sr.Recognizer()
                        with sr.AudioFile(tmp_path) as source:
                            audio = recognizer.record(source)
                        transcribed = clean_transcription(
                            recognizer.recognize_google(audio)
                        )

                        st.markdown(f"**You said:** _{transcribed}_")

                        with st.spinner("Examiner is analyzing your pronunciation..."):
                            feedback = review_pronunciation(practice_text, transcribed)
                            st.markdown("---")
                            st.markdown(feedback)

                    except sr.UnknownValueError:
                        st.error(
                            "Could not understand the audio. "
                            "Please try again and speak clearly."
                        )
                    except sr.RequestError as e:
                        st.error(f"Speech recognition service error: {e}")
                    except LLMError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Review failed: {e}")
                    finally:
                        if tmp_path:
                            Path(tmp_path).unlink(missing_ok=True)

    # ── Tab 2: Save ──────────────────────────────────────────────────

    with tab2:
        st.caption(
            "Save the generated content as interlinked Obsidian notes "
            "(main note + synonym/antonym/collocation/topic sub-notes)."
        )
        if st.button("Save to Vault", type="primary", key="save_btn"):
            try:
                files = save_interlinked(word, content)
                main = files[0]
                st.success(
                    f"Saved: **{main.name}** + {len(files) - 1} linked notes"
                )
                st.caption(f"Output: `{cfg.OUTPUT_DIR}`")
                st.caption(
                    "Sub-folders: `synonyms/` `antonyms/` `collocations/` `topics/`"
                )
            except OSError as e:
                st.error(f"Save failed: {e}")

# ── Footer ───────────────────────────────────────────────────────────

st.divider()
st.caption(
    "CLI mode: `python run.py`  |  Web mode: `streamlit run app.py`  |  "
    f"Model: {cfg.MODEL or '(not set)'}"
)

# ── Hidden radar: cross-page click-to-dictionary ───────────────────────
_render_radar()

