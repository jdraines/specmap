"""Pydantic models for Specmap tracking files.

Matches the .specmap/{branch}.json format.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _generate_mapping_id() -> str:
    """Generate a mapping ID like m_{uuid4_hex[:12]}."""
    return f"m_{uuid.uuid4().hex[:12]}"


class SpecSpan(BaseModel):
    """A span of text within a spec document that a code change implements."""

    spec_file: str
    heading_path: list[str]
    span_offset: int
    span_length: int
    span_hash: str
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)


class CodeTarget(BaseModel):
    """A region of code that implements spec text."""

    file: str
    start_line: int
    end_line: int
    content_hash: str


class Mapping(BaseModel):
    """A mapping between spec text and code."""

    id: str = Field(default_factory=_generate_mapping_id)
    spec_spans: list[SpecSpan] = Field(default_factory=list)
    code_target: CodeTarget
    stale: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SpecSection(BaseModel):
    """A section within a spec document, identified by its heading path."""

    heading_path: list[str]
    heading_line: int
    section_hash: str


class SpecDocument(BaseModel):
    """A parsed spec document with its sections."""

    doc_hash: str
    sections: dict[str, SpecSection] = Field(default_factory=dict)


class SpecmapFile(BaseModel):
    """The top-level .specmap/{branch}.json file."""

    version: int = 1
    branch: str = ""
    base_branch: str = "main"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = "mcp:claude-code"
    spec_documents: dict[str, SpecDocument] = Field(default_factory=dict)
    mappings: list[Mapping] = Field(default_factory=list)
    ignore_patterns: list[str] = Field(default_factory=list)
