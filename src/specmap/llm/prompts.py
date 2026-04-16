"""Prompt templates for LLM-driven annotation generation."""

from __future__ import annotations


_ANNOTATION_SYSTEM = """\
You are an annotation engine that describes code changes and links them to spec documents.

Given code changes and spec document sections, describe what each changed region does in \
natural language. Reference the spec where applicable using [N] notation, where N is a \
sequential number starting from 1.

Additional context from the development session may be provided. Use it to write more \
accurate and informative descriptions — for example, if the developer mentions a specific \
algorithm choice or configuration decision, reflect that in the annotation.

For each annotation, provide:
- file: the code file path
- start_line: first line of the annotated region (1-based)
- end_line: last line of the annotated region (1-based, inclusive)
- description: natural language description with [N] spec references inline
- refs: list of spec references, each with ref_number matching [N] in description, \
spec_file, heading (section title or path like "Auth > Encryption"), \
start_line (line number in spec where excerpt begins), and excerpt (1-3 sentences)
- reasoning: brief explanation of your annotation choices (not stored)

Choose appropriate granularity — group related lines under one description, or give \
individual lines their own annotation when they implement distinct requirements. \
Prefer concise, informative descriptions over verbose ones.

IMPORTANT: When "Changed lines" ranges are shown for a code block, each annotation's \
[start_line, end_line] MUST overlap at least one changed line range. Do not annotate \
unchanged code — only annotate lines that were actually modified or added. The surrounding \
context is provided for understanding but should not be the target of annotations.

Output valid JSON matching the AnnotationResponse schema."""

_SUPPLEMENT_SYSTEM = """\
You are a spec writer that generates concise spec text for code that lacks specification coverage.

Given code content and its file path, write spec text that captures the intent and requirements \
that the code implements. Write in the style of a technical specification, not code documentation."""


def build_annotation_prompt(
    code_changes: list[dict],
    spec_sections: dict[str, list[dict]],
    context: str | None = None,
) -> list[dict]:
    """Build system + user messages for annotating code changes.

    Args:
        code_changes: list of dicts with file_path, start_line, end_line, content
        spec_sections: dict of spec_file -> list of {heading, start_line, content}
        context: optional freeform context from the development session
    """
    code_parts = []
    for change in code_changes:
        header = f"### File: {change['file_path']} (lines {change['start_line']}-{change['end_line']})"
        if change.get("diff_ranges"):
            ranges_str = ", ".join(f"{s}-{e}" for s, e in change["diff_ranges"])
            header += f"\nChanged lines: {ranges_str}"
        code_parts.append(f"{header}\n```\n{change['content']}\n```")
    code_block = "\n\n".join(code_parts)

    spec_parts = []
    for spec_file, sections in spec_sections.items():
        spec_parts.append(f"## Spec: {spec_file}")
        for section in sections:
            spec_parts.append(
                f"### {section['heading']} (line {section['start_line']})\n"
                f"{section['content']}"
            )
    spec_block = "\n\n".join(spec_parts)

    user_message = (
        f"# Code Changes\n\n{code_block}\n\n"
        f"# Spec Documents\n\n{spec_block}\n\n"
    )

    if context:
        user_message += f"# Additional Context\n\n{context}\n\n"

    user_message += (
        "Describe what each code region does and reference spec sections using [N] notation. "
        "Return a JSON object with an 'annotations' array."
    )

    return [
        {"role": "system", "content": _ANNOTATION_SYSTEM},
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
