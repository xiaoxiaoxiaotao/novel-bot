````skill
---
name: summarize
description: Summarize web pages, articles, or local files. Use when user asks to "summarize this link", "what is this file about", or "TL;DR".
---

# Summarize

This skill helps you summarize content from various sources.

## Web Pages

To summarize a URL:
1. Use the `fetch_webpage` tool to get the content.
2. If the content is large, the tool might truncate it. That is usually fine for a summary.
3. specific: "Summarize the following article in 3 bullet points:" or "Give me a detailed summary of..."

## Local Files

To summarize a local file:
1. Use `read_file` to read the content.
2. If the file is huge, read the first 200 lines and the last 200 lines, or skim it in chunks.
3. Provide a summary based on the content.

## You can also summarize specific topics

- "Summarize the changes in `novel_bot/agent/context.py`" -> Read file, compare with memory or diff if possible (using `git diff` via `run_in_terminal` is also an option).

## Output Format

Unless specified otherwise, use this format:

**Title/Topic**

**TL;DR**: One sentence summary.

**Key Points**:
- Point 1
- Point 2
- Point 3

**Conclusion/Takeaway**: Final thought.
````