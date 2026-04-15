"""LLM-driven annotation generation for code changes."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from specmap.indexer.code_analyzer import CodeChange
from specmap.indexer.hasher import hash_code_lines
from specmap.llm.client import LLMClient
from specmap.llm.prompts import build_annotation_prompt
from specmap.llm.schemas import AnnotationResponse
from specmap.state.models import Annotation, SpecRef, _generate_annotation_id


class Mapper:
    """Generates annotations for code changes using LLM."""

    def __init__(self, llm_client: LLMClient, repo_root: str):
        self.llm = llm_client
        self.repo_root = repo_root
        self.completed_batches = 0
        self.total_batches = 0

    async def annotate_changes(
        self,
        changes: list[CodeChange],
        spec_contents: dict[str, str],
        context: str | None = None,
        batch_token_budget: int = 0,
        on_progress: Callable[[int, int], Awaitable[None] | None] | None = None,
        deadline: float | None = None,
        concurrency: int = 1,
    ) -> list[Annotation]:
        """Generate annotations for code changes.

        Batches changes by file to reduce LLM calls. Sends code context + all
        spec sections and lets the LLM generate natural-language annotations
        with inline spec references.

        If batch_token_budget > 0, small files are grouped into multi-file
        batches to reduce LLM call count.

        If deadline is set (time.monotonic value), stops processing before
        starting a new batch once the deadline has passed.

        If concurrency > 1, batches are processed in parallel using a semaphore.
        """
        if not changes:
            return []

        # Group changes by file
        grouped: dict[str, list[CodeChange]] = {}
        for change in changes:
            grouped.setdefault(change.file_path, []).append(change)

        # Build file_contents dict for code_hash computation
        file_contents: dict[str, str] = {}
        for change in changes:
            if change.file_path not in file_contents and change.content:
                file_contents[change.file_path] = change.content

        all_annotations: list[Annotation] = []

        # Build spec sections context (shared across all batches)
        spec_sections = _build_spec_sections(spec_contents)

        # Build batches of file groups
        batches = _build_batches(grouped, batch_token_budget)
        self.total_batches = len(batches)
        self.completed_batches = 0

        if concurrency > 1 and len(batches) > 1:
            # Concurrent batch processing
            all_annotations = await self._process_batches_concurrent(
                batches, grouped, file_contents, spec_sections, context,
                on_progress, deadline, concurrency,
            )
        else:
            # Sequential batch processing
            for batch_idx, batch_files in enumerate(batches):
                if deadline is not None and time.monotonic() > deadline:
                    break

                if on_progress is not None:
                    result = on_progress(batch_idx + 1, len(batches))
                    if result is not None:
                        await result

                annotations = await self._process_single_batch(
                    batch_files, grouped, file_contents, spec_sections, context,
                )
                all_annotations.extend(annotations)
                self.completed_batches = batch_idx + 1

        return all_annotations

    async def _process_single_batch(
        self,
        batch_files: list[str],
        grouped: dict[str, list[CodeChange]],
        file_contents: dict[str, str],
        spec_sections: dict[str, list[dict]],
        context: str | None,
    ) -> list[Annotation]:
        """Process a single batch of files. Returns annotations or empty list on error."""
        code_change_dicts = []
        batch_label_parts = []
        for file_path in batch_files:
            batch_label_parts.append(file_path)
            for c in grouped[file_path]:
                code_change_dicts.append({
                    "file_path": c.file_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "content": c.content,
                })

        messages = build_annotation_prompt(code_change_dicts, spec_sections, context=context)
        batch_label = ", ".join(batch_label_parts)

        try:
            result = await self.llm.complete(
                messages, response_format=AnnotationResponse
            )
            if isinstance(result, AnnotationResponse):
                return _convert_results(result, file_contents)
        except Exception as e:
            print(
                f"[specmap] Warning: LLM annotation failed for {batch_label}: {e}",
                file=sys.stderr,
            )
        return []

    async def _process_batches_concurrent(
        self,
        batches: list[list[str]],
        grouped: dict[str, list[CodeChange]],
        file_contents: dict[str, str],
        spec_sections: dict[str, list[dict]],
        context: str | None,
        on_progress: Callable[[int, int], Awaitable[None] | None] | None,
        deadline: float | None,
        concurrency: int,
    ) -> list[Annotation]:
        """Process batches concurrently with a semaphore."""
        sem = asyncio.Semaphore(concurrency)
        completed = 0

        async def process_batch(batch_idx: int, batch_files: list[str]) -> list[Annotation]:
            nonlocal completed
            if deadline is not None and time.monotonic() > deadline:
                return []
            async with sem:
                if deadline is not None and time.monotonic() > deadline:
                    return []
                annotations = await self._process_single_batch(
                    batch_files, grouped, file_contents, spec_sections, context,
                )
                completed += 1
                self.completed_batches = completed
                if on_progress is not None:
                    result = on_progress(completed, len(batches))
                    if result is not None:
                        await result
                return annotations

        results = await asyncio.gather(
            *[process_batch(i, bf) for i, bf in enumerate(batches)]
        )
        return [ann for batch_result in results for ann in batch_result]


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


def _convert_results(
    response: AnnotationResponse,
    file_contents: dict[str, str] | None = None,
) -> list[Annotation]:
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

        # Compute code_hash if file contents are available
        code_hash = ""
        if file_contents and result.file in file_contents:
            try:
                code_hash = hash_code_lines(
                    file_contents[result.file], result.start_line, result.end_line
                )
            except (IndexError, ValueError):
                pass

        annotation = Annotation(
            id=_generate_annotation_id(),
            file=result.file,
            start_line=result.start_line,
            end_line=result.end_line,
            description=result.description,
            refs=refs,
            created_at=datetime.now(timezone.utc),
            code_hash=code_hash,
        )
        annotations.append(annotation)

    return annotations


def _build_batches(
    grouped: dict[str, list[CodeChange]],
    batch_token_budget: int,
) -> list[list[str]]:
    """Group files into batches for LLM calls.

    If batch_token_budget <= 0, each file gets its own batch (current behavior).
    Otherwise, small files are grouped up to the token budget.
    """
    if batch_token_budget <= 0:
        return [[fp] for fp in grouped]

    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for file_path, file_changes in grouped.items():
        # Estimate tokens as ~chars/4
        file_tokens = sum(len(c.content) // 4 for c in file_changes if c.content)

        if file_tokens >= batch_token_budget:
            # Large file gets its own batch
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            batches.append([file_path])
            continue

        if current_tokens + file_tokens > batch_token_budget and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(file_path)
        current_tokens += file_tokens

    if current_batch:
        batches.append(current_batch)

    return batches
