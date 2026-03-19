"""litellm wrapper with retry and token counting."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import litellm
from pydantic import BaseModel

from specmap_mcp.config import SpecmapConfig


class LLMClient:
    """LLM client wrapping litellm with retry and token tracking."""

    def __init__(self, config: SpecmapConfig):
        self.model = config.model
        self.api_key = config.api_key
        self.api_base = config.api_base
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0

    async def complete(
        self,
        messages: list[dict],
        response_format: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        """Call litellm.acompletion with retry.

        Args:
            messages: Chat messages
            response_format: Optional Pydantic model for structured output

        Returns:
            String response or parsed Pydantic model
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        # Add response_format for structured output
        if response_format is not None:
            kwargs["response_format"] = response_format

        last_error = None
        for attempt in range(3):
            try:
                response = await litellm.acompletion(**kwargs)
                self._call_count += 1

                # Track token usage
                usage = getattr(response, "usage", None)
                if usage:
                    self._total_input_tokens += getattr(usage, "prompt_tokens", 0)
                    self._total_output_tokens += getattr(usage, "completion_tokens", 0)

                content = response.choices[0].message.content

                if response_format is not None:
                    try:
                        return response_format.model_validate_json(content)
                    except Exception:
                        # Try parsing as dict first
                        data = json.loads(content)
                        return response_format.model_validate(data)

                return content

            except (litellm.exceptions.RateLimitError, litellm.exceptions.ServiceUnavailableError) as e:
                last_error = e
                wait = 2**attempt
                print(
                    f"[specmap] LLM call failed (attempt {attempt + 1}/3), "
                    f"retrying in {wait}s: {e}",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait)
            except Exception as e:
                # Non-transient error, don't retry
                raise

        raise last_error  # type: ignore[misc]

    def get_usage(self) -> dict:
        """Return cumulative token counts."""
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_calls": self._call_count,
        }
