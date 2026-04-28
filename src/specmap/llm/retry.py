"""Rate-limit-aware retry utility for LLM calls."""

from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger("specmap.llm")

_RATE_LIMIT_PATTERNS = [
    r"rate.?limit",
    r"too many requests",
    r"429",
    r"requests? per minute",
    r"tokens? per minute",
    r"quota",
    r"retry.?after",
    r"throttl",
]
_RATE_LIMIT_RE = re.compile("|".join(_RATE_LIMIT_PATTERNS), re.IGNORECASE)

_RETRY_AFTER_RE = re.compile(r"retry.?after\D*(\d+)", re.IGNORECASE)


def is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception looks like a rate limit error."""
    return bool(_RATE_LIMIT_RE.search(str(error)))


def extract_wait_seconds(error: Exception) -> int | None:
    """Try to extract a wait time from the error message."""
    m = _RETRY_AFTER_RE.search(str(error))
    return int(m.group(1)) if m else None


async def with_rate_limit_retry(
    coro_factory,
    max_retries: int = 3,
    default_wait: int = 30,
):
    """Call coro_factory() with rate-limit-aware retry.

    Args:
        coro_factory: Zero-arg callable that returns an awaitable.
        max_retries: Maximum number of retries for rate limit errors.
        default_wait: Default wait time in seconds if not extractable from error.

    Non-rate-limit errors are raised immediately without retry.
    """
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            if not is_rate_limit_error(e) or attempt == max_retries:
                raise
            wait = extract_wait_seconds(e) or default_wait * (attempt + 1)
            logger.warning(
                "Rate limit hit (attempt %d/%d), waiting %ds: %s",
                attempt + 1, max_retries, wait, e,
            )
            await asyncio.sleep(wait)


async def resilient_agent_call(agent, prompt, model, rescue_agent, deps=None, usage_limits=None):
    """Run an agent call with rate-limit retry and a rescue fallback on any failure.

    If the primary agent fails (budget exceeded, validation error, etc.),
    the rescue_agent makes a single toolless attempt with the same prompt.
    If that also fails, the original error is re-raised.

    Args:
        agent: The primary pydantic-ai Agent to run.
        prompt: User prompt string.
        model: Model to use.
        rescue_agent: Toolless agent with the same output_type, used as fallback.
        deps: Dependencies for the primary agent (ignored for rescue).
        usage_limits: UsageLimits for the primary agent.
    """
    from pydantic_ai.usage import UsageLimits

    try:
        result = await with_rate_limit_retry(lambda: agent.run(
            user_prompt=prompt,
            model=model,
            deps=deps,
            usage_limits=usage_limits,
        ))
        return result.output
    except Exception as e:
        logger.warning("Agent failed (%s), attempting rescue call", e)
        try:
            rescue = await rescue_agent.run(
                user_prompt=prompt[:50000],
                model=model,
                usage_limits=UsageLimits(request_limit=1),
            )
            return rescue.output
        except Exception as e2:
            logger.error("Rescue call also failed: %s", e2)
            raise e
