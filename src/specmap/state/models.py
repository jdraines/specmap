"""Pydantic models for Specmap tracking files.

Matches the .specmap/{branch}.json format (v2: annotation-based).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _generate_annotation_id() -> str:
    """Generate an annotation ID like a_{uuid4_hex[:12]}."""
    return f"a_{uuid.uuid4().hex[:12]}"


class SpecRef(BaseModel):
    """An inline citation to a spec document within an annotation."""

    id: int  # Reference number within the annotation (1, 2, ...)
    spec_file: str  # "docs/auth-spec.md"
    heading: str  # "Token Storage" or "Authentication > Encryption"
    start_line: int  # Line number in spec file where excerpt begins
    excerpt: str  # Short excerpt of the referenced spec text (1-3 sentences)


class Annotation(BaseModel):
    """A description of a code change region with inline spec references."""

    id: str = Field(default_factory=_generate_annotation_id)
    file: str  # "src/auth/session.go"
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed, inclusive
    description: str  # "Implements session store... [1][2]"
    refs: list[SpecRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    code_hash: str = ""  # sha256: hash of code at [start_line:end_line], "" = legacy/unknown
    staleness: str = ""  # "fresh", "shifted", "stale", "", populated by check_sync/status


class SpecmapFile(BaseModel):
    """The top-level .specmap/{branch}.json file (v2)."""

    version: int = 2
    branch: str = ""
    base_branch: str = "main"
    head_sha: str = ""  # Enables diff-based skip on next push
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = "mcp:claude-code"
    annotations: list[Annotation] = Field(default_factory=list)
    ignore_patterns: list[str] = Field(default_factory=list)
    file_hashes: dict[str, str] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """A single message in a walkthrough step chat."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WalkthroughStep(BaseModel):
    """A single step in a walkthrough."""

    step_number: int
    title: str
    narrative: str
    file: str = ""
    start_line: int = 0
    end_line: int = 0
    refs: list[dict] = Field(default_factory=list)
    chat: list[ChatMessage] = Field(default_factory=list)


class WalkthroughFile(BaseModel):
    """The .specmap/{branch}.walkthrough.json file."""

    version: int = 1
    branch: str = ""
    head_sha: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = "server:generate"
    familiarity: int = 2
    depth: str = "quick"
    summary: str = ""
    steps: list[WalkthroughStep] = Field(default_factory=list)


class CodeReviewIssue(BaseModel):
    """A single issue found during code review."""

    issue_number: int
    severity: str  # "P0", "P1", "P2", "P3", "P4"
    title: str
    description: str  # markdown
    file: str
    start_line: int = 0
    end_line: int = 0
    suggested_fix: str = ""  # markdown with code blocks
    category: str = ""  # "correctness", "security", "performance", "style", "design"
    reasoning: str = ""  # LLM's self-verification reasoning
    chat: list[ChatMessage] = Field(default_factory=list)


class CodeReviewFile(BaseModel):
    """The .specmap/{branch}.code-review.json file."""

    version: int = 1
    branch: str = ""
    head_sha: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = "server:generate"
    summary: str = ""
    issues: list[CodeReviewIssue] = Field(default_factory=list)
