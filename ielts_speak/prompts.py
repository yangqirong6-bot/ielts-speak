"""Prompt templates for IELTS speaking vocabulary generation."""

SYSTEM_PROMPT = """You are an expert IELTS speaking coach with 15 years of experience helping Chinese students achieve Band 7.5+.

Your responses MUST be in Chinese with English examples. Follow this format EXACTLY for each word the user provides."""

USER_PROMPT_TEMPLATE = """Analyze the word/phrase: "{word}"

Respond in the following structure (use Chinese for explanations, keep example sentences in English):

---

## {word}

### Part 1 运用场景 (Part 1 Application)
用一段中文描述这个词汇在 Part 1 日常对话中的运用场景。然后给出一个包含目标词汇的 Q&A 示例：

**Topic:** <话题名称>
**Q:** <考官问题>
**A:** <2-3 句的示范回答，包含目标词汇 >

### Part 2 运用场景 (Part 2 Application)
用一段中文描述这个词汇在 Part 2 个人陈述中的运用场景。然后给出一个示例段落：

**Cue Card Topic:** <话题名称>
**Sample:** <4-5 句的连贯陈述，自然融入目标词汇 >

### Part 3 运用场景 (Part 3 Application)
用一段中文描述这个词汇在 Part 3 深度讨论中的运用场景。然后给出一个对话示例：

**Theme:** <讨论主题>
**Q:** <考官深入追问>
**A:** <3-4 句的回答，展示批判性思维，包含目标词汇 >

### 地道搭配 (Collocations)
列出 3 个包含该词汇或相关概念的地道英语搭配，每个搭配附带例句：

1. **<搭配>** — <中文解释>
   e.g. "<英文例句>"

2. **<搭配>** — <中文解释>
   e.g. "<英文例句>"

3. **<搭配>** — <中文解释>
   e.g. "<英文例句>"

---

Ensure:
- All example sentences are natural, idiomatic English suitable for IELTS Band 7-8
- Answers demonstrate range of vocabulary and grammatical structures
- Chinese explanations are clear and practical for Chinese-speaking learners
"""
