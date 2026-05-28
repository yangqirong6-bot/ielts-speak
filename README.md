# IELTS Speaking Vocabulary Coach

雅思口语词汇陪练工具 — 输入单词，LLM 自动生成 Part 1/2/3 场景用例 + 地道搭配。

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env — fill in your API key and base URL

# 3. Run
python run.py
```

## Configuration

Supports any OpenAI-compatible API:

| Provider | `IELTS_API_BASE` | `IELTS_MODEL` |
|----------|------------------|---------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3` |

## Usage

```text
Enter a word: ambitious

[Loading spinner...]

┌─ IELTS Speaking: ambitious ─────────────────────┐
│ ## ambitious                                      │
│                                                   │
│ ### Part 1 运用场景 ...                            │
│ ### Part 2 运用场景 ...                            │
│ ### Part 3 运用场景 ...                            │
│ ### 地道搭配 (Collocations)                        │
└───────────────────────────────────────────────────┘

Save this result to .md file? [Y/n]: y
Saved: output/ambitious_20260101_120000.md
```

### Commands

| Command | Action |
|---------|--------|
| `:help` | Show help |
| `:list` | List saved .md files |
| `:out` | Show output directory path |
| `:q` | Quit |

## Saved Files

Outputs are saved as Markdown in `output/` with YAML frontmatter (word, date, model info), organized and searchable.
