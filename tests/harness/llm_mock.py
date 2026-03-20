"""Mock litellm.acompletion and response builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from specmap.llm.schemas import AnnotationRef, AnnotationResponse, AnnotationResult


# ---------------------------------------------------------------------------
# Mock response objects matching litellm's response shape
# ---------------------------------------------------------------------------

@dataclass
class MockMessage:
    content: str


@dataclass
class MockChoice:
    message: MockMessage


@dataclass
class MockUsage:
    prompt_tokens: int = 100
    completion_tokens: int = 50


@dataclass
class MockLLMResponse:
    choices: list[MockChoice] = field(default_factory=list)
    usage: MockUsage = field(default_factory=MockUsage)

    @classmethod
    def from_json(cls, json_str: str, prompt_tokens: int = 100, completion_tokens: int = 50):
        return cls(
            choices=[MockChoice(MockMessage(json_str))],
            usage=MockUsage(prompt_tokens, completion_tokens),
        )


# ---------------------------------------------------------------------------
# Response registry
# ---------------------------------------------------------------------------

def _always_true(**kwargs):
    return True


class LLMMockRegistry:
    """Matcher-based mock for litellm.acompletion."""

    def __init__(self):
        self._responses: list[tuple[str, Callable, object]] = []
        self._call_log: list[dict] = []

    # --- registration ---

    def on_annotation(self, response: AnnotationResponse, match_fn: Callable | None = None):
        self._responses.append(("annotation", match_fn or _always_true, response))

    # --- call log inspection ---

    @property
    def call_count(self) -> int:
        return len(self._call_log)

    @property
    def calls(self) -> list[dict]:
        return list(self._call_log)

    @property
    def last_messages(self) -> list[dict] | None:
        """Return the messages from the most recent LLM call, or None."""
        if not self._call_log:
            return None
        return self._call_log[-1].get("messages")

    # --- the mock itself ---

    async def mock_acompletion(self, **kwargs):
        self._call_log.append(kwargs)

        response_format = kwargs.get("response_format")
        call_type = _classify_call(response_format)

        for resp_type, matcher, response_model in self._responses:
            if call_type is not None and resp_type != call_type:
                continue
            if matcher(**kwargs):
                json_str = response_model.model_dump_json()
                return MockLLMResponse.from_json(json_str)

        # Fallback: return an empty-but-valid response
        if call_type == "annotation":
            return MockLLMResponse.from_json(
                AnnotationResponse(annotations=[]).model_dump_json()
            )
        return MockLLMResponse.from_json("{}")


def _classify_call(response_format) -> str | None:
    if response_format is None:
        return None
    name = getattr(response_format, "__name__", "")
    if name == "AnnotationResponse":
        return "annotation"
    return None


# ---------------------------------------------------------------------------
# Helpers: build deterministic LLM responses with correct line numbers
# ---------------------------------------------------------------------------

def _find_heading(spec_content: str, heading_text: str):
    """Return (line_index, heading_level, lines) for the first matching heading."""
    lines = spec_content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        text = stripped.lstrip("#").strip().rstrip("#").strip()
        if text == heading_text:
            return i, level, lines
    return None, None, lines


def _line_offset(lines: list[str], line_idx: int) -> int:
    """Character offset of the start of line_idx (0-based)."""
    return sum(len(lines[j]) + 1 for j in range(line_idx))


def _extract_section_content(spec_content: str, heading_text: str) -> tuple[int, str]:
    """Extract section content and start line for a heading.

    Returns (start_line_1based, section_content).
    """
    line_idx, level, lines = _find_heading(spec_content, heading_text)
    if line_idx is None:
        raise ValueError(f"Heading '{heading_text}' not found in spec content")

    # Find end: next heading of same or higher level
    end_idx = len(lines)
    for i in range(line_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped.startswith("#"):
            continue
        h_level = len(stripped) - len(stripped.lstrip("#"))
        if h_level <= level:
            end_idx = i
            break

    content = "\n".join(lines[line_idx:end_idx]).strip()
    # Extract just the body (skip heading line)
    body_lines = lines[line_idx + 1:end_idx]
    body = "\n".join(body_lines).strip()

    return line_idx + 1, body  # 1-based line number


def build_annotation_for_spec(
    spec_content: str,
    heading_text: str,
    spec_file: str,
    heading_path: str,  # e.g. "Authentication > Token Storage"
    code_file: str,
    code_start: int = 1,
    code_end: int = 31,
    relevance: float = 0.95,
) -> AnnotationResult:
    """Build an AnnotationResult with correct spec references."""
    start_line, excerpt = _extract_section_content(spec_content, heading_text)

    # Truncate excerpt to first 2 sentences
    sentences = excerpt.split(". ")
    if len(sentences) > 2:
        excerpt = ". ".join(sentences[:2]) + "."

    return AnnotationResult(
        file=code_file,
        start_line=code_start,
        end_line=code_end,
        description=f"Implements {heading_text.lower()} functionality. [1]",
        refs=[
            AnnotationRef(
                ref_number=1,
                spec_file=spec_file,
                heading=heading_path,
                start_line=start_line,
                excerpt=excerpt,
            ),
        ],
        reasoning="Mock annotation",
    )
