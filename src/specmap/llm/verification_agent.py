"""Pydantic AI agent for false-positive verification of code review issues.

Uses the same shared codebase tools as the chat agent to independently verify
whether flagged issues are real.
"""

from __future__ import annotations

from pydantic_ai import Agent

from specmap.llm.deps import ChatDeps
from specmap.llm.codebase_tools import CODEBASE_TOOLS
from specmap.llm.verification_prompts import _VERIFICATION_SYSTEM
from specmap.llm.verification_schemas import VerificationResult

# Tool-enabled agent for verification (uses agent.iter() via resilient_agent_call)
verification_agent = Agent(
    deps_type=ChatDeps,
    system_prompt=_VERIFICATION_SYSTEM,
    output_type=VerificationResult,
    retries=4,
    tools=CODEBASE_TOOLS,
)

# Toolless rescue agent (same prompt and output type, no tools)
verification_rescue_agent = Agent(
    system_prompt=_VERIFICATION_SYSTEM,
    output_type=VerificationResult,
    retries=4,
)
