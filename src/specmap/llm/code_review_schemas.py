"""Structured output schemas for code review LLM responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ReviewIssue(BaseModel):
    """A single issue found during code review."""

    issue_number: int  # 1-indexed
    severity: Literal["P0", "P1", "P2", "P3", "P4"]
    title: str  # Short heading
    description: str  # Markdown explanation of the issue
    file: str  # Target file path
    start_line: int  # New-file line number from the diff
    end_line: int | None = None
    suggested_fix: str = ""  # Markdown with code blocks showing the fix
    category: str = ""  # "correctness", "security", "performance", "style", "design"
    reasoning: str = ""  # Not stored — explains severity choice


class CodeReviewResponse(BaseModel):
    """LLM response containing a structured code review."""

    summary: str  # Overall review summary (2-4 sentences)
    issues: list[ReviewIssue]
