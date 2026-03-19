"""Structured output schemas for LLM responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MappingResult(BaseModel):
    """Single mapping from LLM."""

    spec_file: str
    heading_path: list[str]
    span_offset: int
    span_length: int
    relevance: float = Field(ge=0.0, le=1.0)
    reasoning: str  # not stored, for debugging


class MappingResponse(BaseModel):
    """LLM response for mapping code to spec."""

    mappings: list[MappingResult]


class ReindexResult(BaseModel):
    """LLM response for re-indexing a stale mapping."""

    found: bool
    spec_file: str | None = None
    heading_path: list[str] | None = None
    span_offset: int | None = None
    span_length: int | None = None
    relevance: float | None = None
    reasoning: str
