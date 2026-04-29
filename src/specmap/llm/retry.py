"""Rate-limit-aware retry and resilient agent call utilities."""

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


def _extract_failed_output(error: Exception) -> str | None:
    """Try to extract the raw model output from a validation error."""
    msg = str(error)
    # pydantic-ai includes the raw output in some error messages
    for marker in ("output:", "Output:", "response:", "content:"):
        idx = msg.find(marker)
        if idx != -1:
            return msg[idx + len(marker):].strip()[:10000]
    return None


def _is_output_validation_error(error: Exception) -> bool:
    """Check if an error is specifically an output validation failure."""
    msg = str(error).lower()
    return any(phrase in msg for phrase in (
        "output validation",
        "maximum retries",
        "final_result",
        "exceeded maximum retries",
        "validation error",
    ))


def _parse_json_from_text(text: str) -> dict | None:
    """Try to extract and parse JSON from a text string, stripping markdown fences etc."""
    import json

    text = text.strip()

    # Try parsing as-is first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strip markdown code fences
    if "```" in text:
        # Find content between fences
        parts = text.split("```")
        for part in parts[1::2]:  # odd-indexed parts are inside fences
            content = part.strip()
            # Strip language identifier (e.g., "json\n")
            if content.startswith(("json", "JSON")):
                content = content[4:].strip()
            try:
                return json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

    # Find first { ... last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    return None


async def _string_based_fallback(agent_or_model, prompt, model, output_type, max_attempts=2, failed_output=None):
    """Fallback: run agent with output_type=str, parse JSON manually.

    This avoids pydantic-ai's tool-based structured output which can fail
    on large responses. Instead, the model writes plain text JSON and we
    parse it ourselves.
    """
    from pydantic_ai import Agent
    from pydantic_ai.usage import UsageLimits

    # Create a string-output agent with the same system prompt
    str_agent = Agent(
        system_prompt=(
            "You must respond with a valid JSON object matching the required schema. "
            "Do not use markdown fences. Output ONLY the JSON object, nothing else."
        ),
        output_type=str,
        retries=0,
    )

    for attempt in range(max_attempts):
        try:
            if failed_output:
                rescue_prompt = (
                    "A previous attempt produced output that failed validation. "
                    "Produce a valid JSON response matching the CodeReviewResponse schema:\n"
                    '{"summary": "...", "issues": [{"issue_number": 1, "severity": "P0"|"P1"|"P2"|"P3"|"P4", '
                    '"title": "...", "description": "...", "file": "...", "start_line": N, ...}]}\n\n'
                    f"Original request:\n{prompt[:40000]}"
                )
            else:
                rescue_prompt = (
                    "Respond with ONLY a valid JSON object matching the CodeReviewResponse schema:\n"
                    '{"summary": "...", "issues": [{"issue_number": 1, "severity": "P0"|"P1"|"P2"|"P3"|"P4", '
                    '"title": "...", "description": "...", "file": "...", "start_line": N, ...}]}\n\n'
                    f"{prompt[:45000]}"
                )

            result = await str_agent.run(
                user_prompt=rescue_prompt,
                model=model,
                usage_limits=UsageLimits(request_limit=50),
            )

            raw_text = result.output
            parsed = _parse_json_from_text(raw_text)
            if parsed is None:
                logger.warning("String fallback attempt %d/%d: could not parse JSON from response", attempt + 1, max_attempts)
                failed_output = raw_text
                continue

            validated = output_type.model_validate(parsed)
            logger.info("String fallback attempt %d/%d: successfully parsed and validated", attempt + 1, max_attempts)
            return validated

        except Exception as e:
            logger.warning("String fallback attempt %d/%d failed: %s", attempt + 1, max_attempts, e)
            failed_output = _extract_failed_output(e) or failed_output

    return None


async def with_rate_limit_retry(
    coro_factory,
    max_retries: int = 3,
    default_wait: int = 30,
):
    """Call coro_factory() with rate-limit-aware retry.

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


async def _rescue_call(rescue_agent, prompt, model, max_attempts=3, failed_output=None):
    """Make up to max_attempts rescue calls, toolless, with generous limits.

    Includes failed output in the prompt if available to help the model fix validation.
    Returns the output or None if all attempts fail.
    """
    from pydantic_ai.usage import UsageLimits

    for attempt in range(max_attempts):
        try:
            if failed_output:
                rescue_prompt = (
                    "A previous attempt produced invalid output. "
                    "Here is what was produced:\n\n"
                    f"{failed_output[:10000]}\n\n"
                    "Please fix this to match the required JSON schema exactly. "
                    "Original request:\n\n"
                    f"{prompt[:40000]}"
                )
            else:
                rescue_prompt = prompt[:50000]

            result = await rescue_agent.run(
                user_prompt=rescue_prompt,
                model=model,
                usage_limits=UsageLimits(request_limit=50),
            )
            return result.output
        except Exception as e:
            logger.warning("Rescue attempt %d/%d failed: %s", attempt + 1, max_attempts, e)
            failed_output = _extract_failed_output(e) or failed_output
    return None


async def resilient_agent_call(
    agent,
    prompt,
    model,
    rescue_agent,
    deps=None,
    soft_request_limit: int | None = None,
    output_type=None,
):
    """Run an agent with soft budget enforcement and multi-attempt rescue.

    For toolless agents (soft_request_limit=None): runs agent.run() directly.
    For tool agents (soft_request_limit set): uses agent.iter() and breaks out
    at the soft limit, then rescues.

    On output validation failure: falls back to string-based JSON parsing (2 attempts).
    On other failures: rescue_agent makes up to 3 toolless attempts.
    Returns the agent output, or None if everything fails.

    Pass output_type (e.g. CodeReviewResponse) to enable the string-based fallback.
    """
    from pydantic_ai.usage import UsageLimits

    pydantic_ceiling = UsageLimits(request_limit=50)
    failed_output = None

    try:
        if soft_request_limit is not None:
            # Tool agent: enforce soft budget via agent.iter()
            # Inject remaining-budget messages between iterations
            from pydantic_ai.messages import ModelRequest, UserPromptPart

            hit_soft_limit = False
            last_reported = -1
            async with agent.iter(
                user_prompt=prompt,
                model=model,
                deps=deps,
                usage_limits=pydantic_ceiling,
            ) as agent_run:
                async for _node in agent_run:
                    usage = agent_run.usage()
                    remaining = soft_request_limit - usage.requests

                    if usage.requests >= soft_request_limit:
                        logger.info(
                            "Soft budget reached (%d/%d requests), breaking to rescue",
                            usage.requests, soft_request_limit,
                        )
                        hit_soft_limit = True
                        break

                    # Inject budget update when the count changes,
                    # replacing the previous one to avoid stale accumulation
                    if usage.requests != last_reported and usage.requests > 0:
                        last_reported = usage.requests
                        budget_msg = ModelRequest(parts=[UserPromptPart(
                            content=f"[Budget: {remaining}/{soft_request_limit} requests remaining. Each tool use costs 2 requests.]"
                        )])
                        msgs = agent_run.all_messages()
                        # Remove previous budget message if present
                        for i in range(len(msgs) - 1, -1, -1):
                            if (isinstance(msgs[i], ModelRequest)
                                    and len(msgs[i].parts) == 1
                                    and isinstance(msgs[i].parts[0], UserPromptPart)
                                    and str(msgs[i].parts[0].content).startswith("[Budget:")):
                                msgs.pop(i)
                                break
                        msgs.append(budget_msg
                        )

            if not hit_soft_limit and agent_run.result is not None:
                return agent_run.result.output

            # Fell through: either hit soft limit or iter ended without result
            logger.info("Running rescue after soft limit break")
        else:
            # Toolless agent: simple run with rate-limit retry
            result = await with_rate_limit_retry(lambda: agent.run(
                user_prompt=prompt,
                model=model,
                deps=deps,
                usage_limits=pydantic_ceiling,
            ))
            return result.output

    except Exception as e:
        logger.warning("Primary agent call failed: %s", e)
        failed_output = _extract_failed_output(e)

        # For output validation errors, try string-based JSON parsing first
        if _is_output_validation_error(e) and output_type is not None:
            logger.info("Output validation failed — trying string-based JSON fallback")
            result = await _string_based_fallback(
                agent, prompt, model, output_type,
                max_attempts=2, failed_output=failed_output,
            )
            if result is not None:
                return result
            logger.warning("String-based fallback also failed")

    # Rescue: toolless, up to 3 attempts, generous limits
    output = await _rescue_call(rescue_agent, prompt, model, max_attempts=3, failed_output=failed_output)
    return output
