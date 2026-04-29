"""Pydantic AI agents for code review generation.

Three toolless agents form the review pipeline:
- review_agent: Single-call review (Phase 1)
- cross_boundary_agent: Cross-boundary wiring check (Phase 2) — receives pre-computed references
- consolidation_agent: Dedup/validation (Phase 3)
"""

from __future__ import annotations

from pydantic_ai import Agent

from specmap.llm.deps import ChatDeps
from specmap.llm.code_review_prompts import (
    _CODE_REVIEW_SYSTEM,
    _CONSOLIDATION_SYSTEM,
    _CROSS_BOUNDARY_SYSTEM,
)
from specmap.llm.code_review_schemas import CodeReviewResponse

# Reuse ChatDeps for any agent that might need deps in the future
CodeReviewDeps = ChatDeps

# Phase 1: Toolless review — single LLM call
review_agent = Agent(
    system_prompt=_CODE_REVIEW_SYSTEM,
    output_type=CodeReviewResponse,
    retries=4,
)

# Phase 2: Toolless cross-boundary check — receives pre-computed references in prompt
cross_boundary_agent = Agent(
    system_prompt=_CROSS_BOUNDARY_SYSTEM,
    output_type=CodeReviewResponse,
    retries=4,
)

# Phase 3: Toolless consolidation — dedup/validation
consolidation_agent = Agent(
    system_prompt=_CONSOLIDATION_SYSTEM,
    output_type=CodeReviewResponse,
    retries=4,
)
