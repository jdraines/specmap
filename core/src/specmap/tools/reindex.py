"""Selective re-indexing proportional to change size."""

from __future__ import annotations

import sys
from pathlib import Path

from specmap.config import SpecmapConfig
from specmap.indexer.hasher import hash_document, hash_section, hash_span
from specmap.indexer.mapper import Mapper
from specmap.indexer.spec_parser import SpecParser
from specmap.llm.client import LLMClient
from specmap.state.models import Mapping, SpecDocument
from specmap.state.relocator import Relocator
from specmap.state.specmap_file import SpecmapFileManager


async def reindex(
    repo_root: str,
    spec_files: list[str] | None = None,
    code_files: list[str] | None = None,
    force: bool = False,
) -> dict:
    """Selective re-indexing proportional to change size.

    Args:
        repo_root: Path to the repository root
        spec_files: Specific spec files to re-index (None = all known)
        code_files: Specific code files to re-index mappings for (None = all)
        force: If True, re-index everything regardless of hash matches

    Returns:
        Summary with counts of unchanged, relocated, stale, re-mapped
    """
    config = SpecmapConfig.load(repo_root)
    file_mgr = SpecmapFileManager(repo_root)
    parser = SpecParser()
    relocator = Relocator()

    specmap = file_mgr.load()

    # Determine which spec files to check
    if spec_files is None:
        spec_files = list(specmap.spec_documents.keys())

    if not spec_files:
        return {
            "status": "ok",
            "message": "No spec files to re-index",
            "unchanged": 0,
            "relocated": 0,
            "stale": 0,
            "remapped": 0,
        }

    # Track counts
    unchanged_count = 0
    relocated_count = 0
    stale_count = 0
    remapped_count = 0
    docs_skipped = 0
    sections_skipped = 0

    # Old spec contents from stored hashes (we need current file content)
    new_spec_contents: dict[str, str] = {}
    new_spec_docs: dict[str, SpecDocument] = {}

    for sf in spec_files:
        content = _read_file(repo_root, sf)
        if content is None:
            continue
        new_spec_contents[sf] = content
        new_spec_docs[sf] = parser.parse(content, sf)

    # Step 1: Compare document-level hashes -> skip unchanged docs
    changed_spec_files: list[str] = []
    for sf in spec_files:
        if sf not in new_spec_docs:
            continue

        old_doc = specmap.spec_documents.get(sf)
        new_doc = new_spec_docs[sf]

        if not force and old_doc and old_doc.doc_hash == new_doc.doc_hash:
            docs_skipped += 1
            continue

        changed_spec_files.append(sf)

    if not changed_spec_files and not force:
        # No spec changes detected
        file_mgr.save(specmap)
        return {
            "status": "ok",
            "message": "All spec documents unchanged",
            "unchanged": len(specmap.mappings),
            "relocated": 0,
            "stale": 0,
            "remapped": 0,
            "docs_skipped": docs_skipped,
        }

    # Step 2: For changed docs, compare section hashes
    changed_sections: dict[str, set[str]] = {}  # spec_file -> set of changed section keys
    for sf in changed_spec_files:
        old_doc = specmap.spec_documents.get(sf)
        new_doc = new_spec_docs[sf]

        sf_changed_sections: set[str] = set()
        for section_key, new_section in new_doc.sections.items():
            if force:
                sf_changed_sections.add(section_key)
                continue

            if old_doc and section_key in old_doc.sections:
                old_section = old_doc.sections[section_key]
                if old_section.section_hash == new_section.section_hash:
                    sections_skipped += 1
                    continue

            sf_changed_sections.add(section_key)

        if sf_changed_sections:
            changed_sections[sf] = sf_changed_sections

    # Step 3: Find affected mappings (those with spans in changed sections)
    affected_mappings: list[Mapping] = []
    unaffected_mappings: list[Mapping] = []

    for mapping in specmap.mappings:
        # Filter by code_files if specified
        if code_files and mapping.code_target.file not in code_files:
            unaffected_mappings.append(mapping)
            continue

        is_affected = False
        for span in mapping.spec_spans:
            if span.spec_file in changed_sections:
                heading_key = " > ".join(span.heading_path)
                if heading_key in changed_sections[span.spec_file] or force:
                    is_affected = True
                    break

        if is_affected or force:
            affected_mappings.append(mapping)
        else:
            unaffected_mappings.append(mapping)
            unchanged_count += 1

    # Step 4: Try to relocate affected mappings
    if affected_mappings:
        # Build old contents from current stored state
        old_contents: dict[str, str] = {}
        for sf in changed_spec_files:
            # We use the new content for both since we don't store old content
            # The relocator compares span hashes
            if sf in new_spec_contents:
                old_contents[sf] = new_spec_contents[sf]

        relocated, stale = relocator.relocate_mappings(
            affected_mappings, old_contents, new_spec_contents
        )
        relocated_count = len(relocated)
        stale_count = len(stale)

        # Step 5: Try LLM re-mapping for stale mappings
        if stale:
            try:
                llm_client = LLMClient(config)
                mapper = Mapper(llm_client, repo_root)
                remapped = await mapper.remap_stale(stale, new_spec_contents)

                # Count how many were actually remapped (no longer stale)
                still_stale = [m for m in remapped if m.stale]
                actually_remapped = [m for m in remapped if not m.stale]
                remapped_count = len(actually_remapped)
                stale_count = len(still_stale)

                # Replace stale with remapped results
                stale = remapped
            except Exception as e:
                print(f"[specmap] Warning: LLM re-indexing failed: {e}", file=sys.stderr)

        # Rebuild mappings list
        specmap.mappings = unaffected_mappings + relocated + stale
    else:
        unchanged_count = len(unaffected_mappings)

    # Update spec documents
    specmap.spec_documents.update(new_spec_docs)

    file_mgr.save(specmap)

    return {
        "status": "ok",
        "unchanged": unchanged_count,
        "relocated": relocated_count,
        "stale": stale_count,
        "remapped": remapped_count,
        "docs_skipped": docs_skipped,
        "sections_skipped": sections_skipped,
        "total_mappings": len(specmap.mappings),
    }


def _read_file(repo_root: str, file_path: str) -> str | None:
    """Read a file from the repo."""
    try:
        return (Path(repo_root) / file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
