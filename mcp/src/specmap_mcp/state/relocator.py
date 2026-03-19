"""Stale span relocation using fuzzy matching."""

from __future__ import annotations

import difflib

from specmap_mcp.indexer.hasher import hash_span
from specmap_mcp.state.models import Mapping, SpecSpan


_FUZZY_THRESHOLD = 0.8


class Relocator:
    """Relocates spec spans when spec documents change."""

    def relocate_span(
        self, span: SpecSpan, old_content: str, new_content: str
    ) -> SpecSpan | None:
        """Try to find the span's text in the new content.

        Strategy:
        1. Exact match at same offset
        2. Exact match anywhere in the section (identified by heading_path)
        3. Fuzzy match (SequenceMatcher, threshold 0.8)

        Returns updated SpecSpan or None if relocation fails.
        """
        # Extract the original span text from old content
        if span.span_offset + span.span_length > len(old_content):
            return None
        original_text = old_content[span.span_offset : span.span_offset + span.span_length]

        if not original_text.strip():
            return None

        # Strategy 1: exact match at same offset
        if span.span_offset + span.span_length <= len(new_content):
            candidate = new_content[span.span_offset : span.span_offset + span.span_length]
            if candidate == original_text:
                new_hash = hash_span(new_content, span.span_offset, span.span_length)
                return span.model_copy(update={
                    "span_hash": new_hash,
                })

        # Strategy 2: exact match anywhere in new content
        idx = new_content.find(original_text)
        if idx >= 0:
            new_hash = hash_span(new_content, idx, len(original_text))
            return span.model_copy(update={
                "span_offset": idx,
                "span_length": len(original_text),
                "span_hash": new_hash,
            })

        # Strategy 3: fuzzy match
        return self._fuzzy_relocate(span, original_text, new_content)

    def _fuzzy_relocate(
        self, span: SpecSpan, original_text: str, new_content: str
    ) -> SpecSpan | None:
        """Try fuzzy matching to relocate the span."""
        best_ratio = 0.0
        best_offset = -1
        best_length = 0
        original_len = len(original_text)

        # Slide a window of similar size through new content
        # Try windows of 80% to 120% the original length
        for length_factor in [1.0, 0.9, 1.1, 0.8, 1.2]:
            window_size = max(1, int(original_len * length_factor))
            step = max(1, window_size // 4)

            for offset in range(0, max(1, len(new_content) - window_size + 1), step):
                candidate = new_content[offset : offset + window_size]
                ratio = difflib.SequenceMatcher(None, original_text, candidate).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_offset = offset
                    best_length = window_size

        if best_ratio >= _FUZZY_THRESHOLD and best_offset >= 0:
            new_hash = hash_span(new_content, best_offset, best_length)
            return span.model_copy(update={
                "span_offset": best_offset,
                "span_length": best_length,
                "span_hash": new_hash,
            })

        return None

    def relocate_mappings(
        self,
        mappings: list[Mapping],
        old_contents: dict[str, str],
        new_contents: dict[str, str],
    ) -> tuple[list[Mapping], list[Mapping]]:
        """Relocate all spans in mappings.

        Returns (relocated, stale) - relocated have updated spans,
        stale couldn't be relocated.
        """
        relocated: list[Mapping] = []
        stale: list[Mapping] = []

        for mapping in mappings:
            all_relocated = True
            new_spans: list[SpecSpan] = []

            for span in mapping.spec_spans:
                old_content = old_contents.get(span.spec_file)
                new_content = new_contents.get(span.spec_file)

                if old_content is None or new_content is None:
                    all_relocated = False
                    new_spans.append(span)
                    continue

                new_span = self.relocate_span(span, old_content, new_content)
                if new_span is not None:
                    new_spans.append(new_span)
                else:
                    all_relocated = False
                    new_spans.append(span)

            updated = mapping.model_copy(update={
                "spec_spans": new_spans,
                "stale": not all_relocated,
            })

            if all_relocated:
                relocated.append(updated)
            else:
                stale.append(updated)

        return relocated, stale
