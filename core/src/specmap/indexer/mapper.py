"""LLM-driven semantic mapping between spec text and code changes."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from specmap.indexer.code_analyzer import CodeChange
from specmap.indexer.hasher import hash_code, hash_span
from specmap.llm.client import LLMClient
from specmap.llm.prompts import build_mapping_prompt, build_reindex_prompt
from specmap.llm.schemas import MappingResponse, ReindexResult
from specmap.state.models import (
    CodeTarget,
    Mapping,
    SpecDocument,
    SpecSpan,
    _generate_mapping_id,
)


class Mapper:
    """Maps code changes to spec sections using LLM."""

    def __init__(self, llm_client: LLMClient, repo_root: str):
        self.llm = llm_client
        self.repo_root = repo_root

    async def map_changes_to_specs(
        self,
        changes: list[CodeChange],
        spec_docs: dict[str, SpecDocument],
        spec_contents: dict[str, str],
    ) -> list[Mapping]:
        """Map code changes to spec sections.

        Batches changes by file to reduce LLM calls. Sends code context + all
        potentially relevant spec sections and lets the LLM identify mappings.
        """
        if not changes or not spec_docs:
            return []

        # Group changes by file
        grouped: dict[str, list[CodeChange]] = {}
        for change in changes:
            grouped.setdefault(change.file_path, []).append(change)

        all_mappings: list[Mapping] = []

        # Build spec sections context (shared across all batches)
        spec_sections = self._build_spec_context(spec_docs, spec_contents)

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

            messages = build_mapping_prompt(code_change_dicts, spec_sections)

            try:
                result = await self.llm.complete(messages, response_format=MappingResponse)
                if isinstance(result, MappingResponse):
                    mappings = self._convert_results(
                        result, file_changes, spec_contents
                    )
                    all_mappings.extend(mappings)
            except Exception as e:
                print(
                    f"[specmap] Warning: LLM mapping failed for {file_path}: {e}",
                    file=sys.stderr,
                )

        return all_mappings

    async def remap_stale(
        self,
        stale_mappings: list[Mapping],
        spec_contents: dict[str, str],
    ) -> list[Mapping]:
        """Re-map stale mappings by sending code + updated spec to LLM."""
        remapped: list[Mapping] = []

        for mapping in stale_mappings:
            # Get the code content for context
            code_file = mapping.code_target.file
            from specmap.indexer.code_analyzer import CodeAnalyzer

            analyzer = CodeAnalyzer()
            code_content = analyzer.get_file_content(self.repo_root, code_file)
            if code_content is None:
                remapped.append(mapping)
                continue

            # Get relevant spec content
            spec_files_for_mapping = {s.spec_file for s in mapping.spec_spans}
            combined_spec = ""
            for sf in spec_files_for_mapping:
                if sf in spec_contents:
                    combined_spec += f"\n## {sf}\n{spec_contents[sf]}"

            if not combined_spec:
                remapped.append(mapping)
                continue

            # Extract the code region
            lines = code_content.splitlines(keepends=True)
            start = max(0, mapping.code_target.start_line - 1)
            end = min(len(lines), mapping.code_target.end_line)
            code_region = "".join(lines[start:end])

            messages = build_reindex_prompt(mapping, code_region, combined_spec)

            try:
                result = await self.llm.complete(messages, response_format=ReindexResult)
                if isinstance(result, ReindexResult) and result.found:
                    if (
                        result.spec_file
                        and result.heading_path
                        and result.span_offset is not None
                        and result.span_length is not None
                    ):
                        full_content = spec_contents.get(result.spec_file, "")
                        span_h = hash_span(
                            full_content, result.span_offset, result.span_length
                        )
                        new_span = SpecSpan(
                            spec_file=result.spec_file,
                            heading_path=result.heading_path,
                            span_offset=result.span_offset,
                            span_length=result.span_length,
                            span_hash=span_h,
                            relevance=result.relevance or 1.0,
                        )
                        updated = mapping.model_copy(update={
                            "spec_spans": [new_span],
                            "stale": False,
                        })
                        remapped.append(updated)
                        continue
            except Exception as e:
                print(
                    f"[specmap] Warning: LLM remap failed for {code_file}: {e}",
                    file=sys.stderr,
                )

            # Keep as stale if remap failed
            remapped.append(mapping)

        return remapped

    def _build_spec_context(
        self,
        spec_docs: dict[str, SpecDocument],
        spec_contents: dict[str, str],
    ) -> dict[str, dict]:
        """Build spec sections context for prompts."""
        spec_sections: dict[str, dict] = {}

        for spec_file, doc in spec_docs.items():
            content = spec_contents.get(spec_file, "")
            if not content:
                continue

            file_sections: dict[str, dict] = {}
            for section_key, section in doc.sections.items():
                # Find section content by locating the heading line and extracting to next section
                lines = content.split("\n")
                heading_idx = section.heading_line - 1  # 0-based
                if heading_idx < 0 or heading_idx >= len(lines):
                    continue

                # Calculate character offset of this heading
                offset = sum(len(lines[i]) + 1 for i in range(heading_idx))

                # Find section end (next heading of same or higher level, or EOF)
                section_end = len(content)
                level = len(section.heading_path)
                for j in range(heading_idx + 1, len(lines)):
                    line = lines[j].strip()
                    if line.startswith("#"):
                        hashes = len(line) - len(line.lstrip("#"))
                        if hashes <= level:
                            section_end = sum(len(lines[i]) + 1 for i in range(j))
                            break

                section_content = content[offset:section_end]
                file_sections[section_key] = {
                    "heading_path": section.heading_path,
                    "content": section_content,
                    "offset": offset,
                }

            if file_sections:
                spec_sections[spec_file] = file_sections

        return spec_sections

    def _convert_results(
        self,
        response: MappingResponse,
        changes: list[CodeChange],
        spec_contents: dict[str, str],
    ) -> list[Mapping]:
        """Convert LLM MappingResponse to Mapping models."""
        mappings: list[Mapping] = []

        for llm_mapping in response.mappings:
            # Find the best matching code change for this mapping
            # For simplicity, use the first change from this file batch
            if not changes:
                continue

            change = changes[0]
            for c in changes:
                if c.file_path == llm_mapping.spec_file:
                    change = c
                    break

            # Compute hashes
            full_content = spec_contents.get(llm_mapping.spec_file, "")
            span_h = hash_span(full_content, llm_mapping.span_offset, llm_mapping.span_length)
            code_h = hash_code(change.content)

            spec_span = SpecSpan(
                spec_file=llm_mapping.spec_file,
                heading_path=llm_mapping.heading_path,
                span_offset=llm_mapping.span_offset,
                span_length=llm_mapping.span_length,
                span_hash=span_h,
                relevance=llm_mapping.relevance,
            )

            mapping = Mapping(
                id=_generate_mapping_id(),
                spec_spans=[spec_span],
                code_target=CodeTarget(
                    file=change.file_path,
                    start_line=change.start_line,
                    end_line=change.end_line,
                    content_hash=code_h,
                ),
                stale=False,
                created_at=datetime.now(timezone.utc),
            )
            mappings.append(mapping)

        return mappings
