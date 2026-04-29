"""Structured output schema for issue verification."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class VerificationResult(BaseModel):
    """Result of verifying a single code review issue against the actual codebase."""

    verdict: Literal["confirmed", "false_positive", "downgrade"]
    reasoning: str  # Markdown explanation of evidence found
    updated_severity: str | None = None  # Required when verdict == "downgrade"
    updated_description: str | None = None  # Optional refined description
