"""Mock litellm.acompletion and response builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from specmap.llm.schemas import MappingResponse, MappingResult, ReindexResult


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

    def on_mapping(self, response: MappingResponse, match_fn: Callable | None = None):
        self._responses.append(("mapping", match_fn or _always_true, response))

    def on_reindex(self, response: ReindexResult, match_fn: Callable | None = None):
        self._responses.append(("reindex", match_fn or _always_true, response))

    # --- call log inspection ---

    @property
    def call_count(self) -> int:
        return len(self._call_log)

    @property
    def calls(self) -> list[dict]:
        return list(self._call_log)

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
        if call_type == "mapping":
            return MockLLMResponse.from_json(MappingResponse(mappings=[]).model_dump_json())
        if call_type == "reindex":
            return MockLLMResponse.from_json(
                ReindexResult(found=False, reasoning="no mock matched").model_dump_json()
            )
        return MockLLMResponse.from_json("{}")


def _classify_call(response_format) -> str | None:
    if response_format is None:
        return None
    name = getattr(response_format, "__name__", "")
    if name == "MappingResponse":
        return "mapping"
    if name == "ReindexResult":
        return "reindex"
    return None


# ---------------------------------------------------------------------------
# Helpers: build deterministic LLM responses with correct offsets
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


def build_mapping_for_spec(
    spec_content: str,
    heading_text: str,
    spec_file: str,
    heading_path: list[str],
    relevance: float = 0.95,
) -> MappingResult:
    """Build a MappingResult with correct span_offset/span_length for a spec heading."""
    line_idx, level, lines = _find_heading(spec_content, heading_text)
    if line_idx is None:
        raise ValueError(f"Heading '{heading_text}' not found in spec content")

    heading_offset = _line_offset(lines, line_idx)

    # Find end: next heading of same or higher (numerically <=) level
    section_end = len(spec_content)
    for i in range(line_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped.startswith("#"):
            continue
        h_level = len(stripped) - len(stripped.lstrip("#"))
        if h_level <= level:
            section_end = _line_offset(lines, i)
            break

    return MappingResult(
        spec_file=spec_file,
        heading_path=heading_path,
        span_offset=heading_offset,
        span_length=section_end - heading_offset,
        relevance=relevance,
        reasoning="Mock mapping",
    )


def build_reindex_result(
    spec_content: str,
    heading_text: str,
    spec_file: str,
    heading_path: list[str],
    relevance: float = 0.95,
) -> ReindexResult:
    """Build a ReindexResult with correct span_offset/span_length."""
    line_idx, level, lines = _find_heading(spec_content, heading_text)
    if line_idx is None:
        return ReindexResult(found=False, reasoning=f"Heading '{heading_text}' not found")

    heading_offset = _line_offset(lines, line_idx)
    section_end = len(spec_content)
    for i in range(line_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped.startswith("#"):
            continue
        h_level = len(stripped) - len(stripped.lstrip("#"))
        if h_level <= level:
            section_end = _line_offset(lines, i)
            break

    return ReindexResult(
        found=True,
        spec_file=spec_file,
        heading_path=heading_path,
        span_offset=heading_offset,
        span_length=section_end - heading_offset,
        relevance=relevance,
        reasoning="Mock reindex",
    )
