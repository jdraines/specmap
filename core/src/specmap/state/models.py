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
