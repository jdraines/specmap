"""LLM-driven annotation generation for code changes."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from specmap.indexer.code_analyzer import CodeChange
from specmap.llm.client import LLMClient
from specmap.llm.prompts import build_annotation_prompt
from specmap.llm.schemas import AnnotationResponse
from specmap.state.models import Annotation, SpecRef, _generate_annotation_id


class Mapper:
    """Generates annotations for code changes using LLM."""

    def __init__(self, llm_client: LLMClient, repo_root: str):
        self.llm = llm_client
        self.repo_root = repo_root

    async def annotate_changes(
        self,
        changes: list[CodeChange],
        spec_contents: dict[str, str],
    ) -> list[Annotation]:
        """Generate annotations for code changes.

        Batches changes by file to reduce LLM calls. Sends code context + all
        spec sections and lets the LLM generate natural-language annotations
        with inline spec references.
        """
        if not changes:
            return []

        # Group changes by file
        grouped: dict[str, list[CodeChange]] = {}
        for change in changes:
            grouped.setdefault(change.file_path, []).append(change)

        all_annotations: list[Annotation] = []

        # Build spec sections context (shared across all batches)
        spec_sections = _build_spec_sections(spec_contents)

        # Process each file's changes as a batch
        for file_path, file_changes in grouped.items():
            code_change_dicts = [
                {
                    "file_path": c.file_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "content": c.content,
                }
                for c in file_changes
            ]

            messages = build_annotation_prompt(code_change_dicts, spec_sections)

            try:
                result = await self.llm.complete(
                    messages, response_format=AnnotationResponse
                )
                if isinstance(result, AnnotationResponse):
                    annotations = _convert_results(result)
                    all_annotations.extend(annotations)
            except Exception as e:
                print(
                    f"[specmap] Warning: LLM annotation failed for {file_path}: {e}",
                    file=sys.stderr,
                )

        return all_annotations


def _build_spec_sections(
    spec_contents: dict[str, str],
) -> dict[str, list[dict]]:
    """Build spec sections context for prompts from raw spec file contents.

    Parses markdown headings to extract sections with their line numbers.
    """
    spec_sections: dict[str, list[dict]] = {}

    for spec_file, content in spec_contents.items():
        if not content:
            continue

        lines = content.split("\n")
        sections: list[dict] = []

        # Find all headings and extract their content
        heading_indices: list[tuple[int, int, str]] = []  # (line_idx, level, text)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") and not stripped.startswith("#!"):
                level = len(stripped) - len(stripped.lstrip("#"))
                text = stripped.lstrip("#").strip().rstrip("#").strip()
                if text:
                    heading_indices.append((i, level, text))

        for idx, (line_idx, level, text) in enumerate(heading_indices):
            # Find section end: next heading of same or higher level
            end_idx = len(lines)
            for j in range(idx + 1, len(heading_indices)):
                if heading_indices[j][1] <= level:
                    end_idx = heading_indices[j][0]
                    break

            section_content = "\n".join(lines[line_idx:end_idx])
            sections.append({
                "heading": text,
                "start_line": line_idx + 1,  # 1-based
                "content": section_content,
            })

        if sections:
            spec_sections[spec_file] = sections

    return spec_sections


def _convert_results(response: AnnotationResponse) -> list[Annotation]:
    """Convert LLM AnnotationResponse to Annotation models."""
    annotations: list[Annotation] = []

    for result in response.annotations:
        refs = [
            SpecRef(
                id=ref.ref_number,
                spec_file=ref.spec_file,
                heading=ref.heading,
                start_line=ref.start_line,
                excerpt=ref.excerpt,
            )
            for ref in result.refs
        ]

        annotation = Annotation(
            id=_generate_annotation_id(),
            file=result.file,
            start_line=result.start_line,
            end_line=result.end_line,
            description=result.description,
            refs=refs,
            created_at=datetime.now(timezone.utc),
        )
        annotations.append(annotation)

    return annotations
