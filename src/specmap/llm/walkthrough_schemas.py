"""Structured output schemas for walkthrough LLM responses."""

from __future__ import annotations

from pydantic import BaseModel


class WalkthroughRef(BaseModel):
    """A spec reference within a walkthrough step."""

    ref_number: int
    spec_file: str
    heading: str
    excerpt: str


class WalkthroughStep(BaseModel):
    """Single step in a guided walkthrough."""

    step_number: int  # 1-indexed
    title: str  # Short heading ("Setting up the auth middleware")
    narrative: str  # Markdown with [N] spec refs
    file: str  # Target file path
    start_line: int | None = None  # Optional focus range
    end_line: int | None = None
    refs: list[WalkthroughRef] = []
    reasoning: str  # Not stored


class WalkthroughResponse(BaseModel):
    """LLM response containing a guided PR walkthrough."""

    summary: str  # 2-3 sentence PR summary for banner
    steps: list[WalkthroughStep]
