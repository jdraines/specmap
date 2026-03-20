"""Structured output schemas for LLM responses."""

from __future__ import annotations

from pydantic import BaseModel


class AnnotationRef(BaseModel):
    """A spec reference within an annotation result."""

    ref_number: int  # Matches [N] in description
    spec_file: str
    heading: str
    start_line: int  # Line in spec where excerpt begins
    excerpt: str  # Short excerpt (1-3 sentences)


class AnnotationResult(BaseModel):
    """Single annotation from LLM describing a code region."""

    file: str
    start_line: int
    end_line: int
    description: str  # Natural language with [N] references
    refs: list[AnnotationRef]
    reasoning: str  # Not stored, for debugging


class AnnotationResponse(BaseModel):
    """LLM response containing annotations for code regions."""

    annotations: list[AnnotationResult]
