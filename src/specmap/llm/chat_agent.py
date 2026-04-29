"""Pydantic AI agent for walkthrough step chat."""

from __future__ import annotations

from pydantic_ai import Agent

from specmap.llm.codebase_tools import CODEBASE_TOOLS
from specmap.llm.deps import ChatDeps

# Re-export ChatDeps so existing imports from chat_agent still work
__all__ = ["ChatDeps", "chat_agent"]

_SYSTEM_PROMPT = """\
You are an assistant helping a user understand a pull request. The user may be \
on a guided walkthrough or reviewing code review findings. They may ask about \
code, rationale behind changes, spec documents, or the validity of flagged issues.

You have tools to search annotations, grep the codebase, list files, and read \
files. Use them proactively — don't speculate when you can verify.

When a file was changed in this PR, read_file will include both the current \
content and the diff showing what changed. Use the diff to understand what \
was modified.

Think critically. If you gather evidence that contradicts a claim (including \
claims made by an AI code review), say so directly. Do not defer to prior \
analysis when your own investigation shows otherwise.

Be concise. Reference specific files, lines, and spec sections.
Format responses in markdown."""

chat_agent = Agent(
    deps_type=ChatDeps,
    system_prompt=_SYSTEM_PROMPT,
    retries=2,
    tools=CODEBASE_TOOLS,
)
