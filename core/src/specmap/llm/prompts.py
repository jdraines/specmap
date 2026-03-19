"""Prompt templates for LLM-driven mapping and re-indexing."""

from __future__ import annotations

from specmap.state.models import Mapping


_MAPPING_SYSTEM = """\
You are a mapping engine that identifies which spec text describes the intent behind code changes.

Given code changes and spec document sections, identify the specific spans of spec text that \
describe WHY the code exists or what requirement it implements.

For each mapping, provide:
- spec_file: the spec document file path
- heading_path: the hierarchy of headings leading to the relevant section
- span_offset: character offset of the relevant text within the full spec document
- span_length: length of the relevant text span
- relevance: 0.0 to 1.0 indicating how directly the spec text describes this code
- reasoning: brief explanation of why this mapping exists

Output valid JSON matching the MappingResponse schema. Only include mappings where \
you are confident the spec text describes the intent behind the code. \
Prefer precise, narrow spans over broad ones."""

_REINDEX_SYSTEM = """\
You are a mapping engine that re-locates spec text that has moved or changed.

Given a code region and updated spec content, determine if the spec still describes \
the intent behind the code. If so, provide the updated span location.

Output valid JSON matching the ReindexResult schema."""

_SUPPLEMENT_SYSTEM = """\
You are a spec writer that generates concise spec text for code that lacks specification coverage.

Given code content and its file path, write spec text that captures the intent and requirements \
that the code implements. Write in the style of a technical specification, not code documentation."""


def build_mapping_prompt(
    code_changes: list[dict],
    spec_sections: dict[str, dict],
) -> list[dict]:
    """Build system + user messages for mapping code to spec.

    Args:
        code_changes: list of dicts with file_path, start_line, end_line, content
        spec_sections: dict of spec_file -> {section_key -> {heading_path, content, offset}}
    """
    # Build the user message with code and spec context
    code_parts = []
    for change in code_changes:
        code_parts.append(
            f"### File: {change['file_path']} (lines {change['start_line']}-{change['end_line']})\n"
            f"```\n{change['content']}\n```"
        )
    code_block = "\n\n".join(code_parts)

    spec_parts = []
    for spec_file, sections in spec_sections.items():
        spec_parts.append(f"## Spec: {spec_file}")
        for section_key, section_info in sections.items():
            spec_parts.append(
                f"### {section_key} (offset: {section_info['offset']}, "
                f"length: {len(section_info['content'])})\n"
                f"{section_info['content']}"
            )
    spec_block = "\n\n".join(spec_parts)

    user_message = (
        f"# Code Changes\n\n{code_block}\n\n"
        f"# Spec Documents\n\n{spec_block}\n\n"
        "Identify which spec spans describe the intent behind these code changes. "
        "Return a JSON object with a 'mappings' array."
    )

    return [
        {"role": "system", "content": _MAPPING_SYSTEM},
        {"role": "user", "content": user_message},
    ]


def build_reindex_prompt(
    stale_mapping: Mapping,
    code_content: str,
    spec_content: str,
) -> list[dict]:
    """Build prompt for remapping a stale mapping."""
    spans_desc = []
    for span in stale_mapping.spec_spans:
        spans_desc.append(
            f"- Spec file: {span.spec_file}, "
            f"Heading: {' > '.join(span.heading_path)}, "
            f"Previous offset: {span.span_offset}, length: {span.span_length}"
        )
    spans_block = "\n".join(spans_desc)

    user_message = (
        f"# Code Region\n"
        f"File: {stale_mapping.code_target.file} "
        f"(lines {stale_mapping.code_target.start_line}-{stale_mapping.code_target.end_line})\n"
        f"```\n{code_content}\n```\n\n"
        f"# Previous Spec Spans\n{spans_block}\n\n"
        f"# Updated Spec Content\n{spec_content}\n\n"
        "Does the spec still describe the intent behind this code? "
        "If so, provide the updated span location. Return a JSON object matching ReindexResult."
    )

    return [
        {"role": "system", "content": _REINDEX_SYSTEM},
        {"role": "user", "content": user_message},
    ]


def build_supplement_prompt(code_content: str, file_path: str) -> list[dict]:
    """Build prompt for generating spec text for unmapped code (Phase 4 prep, stub)."""
    user_message = (
        f"# Code\nFile: {file_path}\n```\n{code_content}\n```\n\n"
        "Write concise spec text that captures the intent and requirements "
        "this code implements."
    )

    return [
        {"role": "system", "content": _SUPPLEMENT_SYSTEM},
        {"role": "user", "content": user_message},
    ]
