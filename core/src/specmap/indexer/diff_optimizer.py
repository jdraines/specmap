"""Hunk-level optimization for incremental annotation updates.

Parses incremental diffs to classify existing annotations as:
- Overlapping a changed hunk → regenerate (send to LLM)
- Non-overlapping but below changes → shift line numbers mechanically
- Non-overlapping above all hunks → keep verbatim
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from specmap.state.models import Annotation


@dataclass
class Hunk:
    """A changed region from a unified diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int

    @property
    def delta(self) -> int:
        """Net line change: positive = lines added, negative = lines removed."""
        return self.new_count - self.old_count


@dataclass
class FileHunks:
    """All hunks for a single file in a diff."""

    file_path: str
    hunks: list[Hunk]


def parse_incremental_diff(diff_text: str) -> dict[str, FileHunks]:
    """Parse a unified diff into per-file hunk lists.

    Expects output from `git diff {old_sha}..{new_sha}`.
    """
    result: dict[str, FileHunks] = {}

    file_re = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
    hunk_re = re.compile(
        r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE
    )

    current_file = ""
    for line in diff_text.splitlines():
        m = file_re.match(line)
        if m:
            current_file = m.group(1)
            if current_file == "/dev/null":
                current_file = ""
            continue

        if not current_file:
            continue

        m = hunk_re.match(line)
        if m:
            hunk = Hunk(
                old_start=int(m.group(1)),
                old_count=int(m.group(2)) if m.group(2) else 1,
                new_start=int(m.group(3)),
                new_count=int(m.group(4)) if m.group(4) else 1,
            )
            if current_file not in result:
                result[current_file] = FileHunks(file_path=current_file, hunks=[])
            result[current_file].hunks.append(hunk)

    return result


@dataclass
class ClassifiedAnnotations:
    """Annotations classified by their relationship to changed hunks."""

    keep: list[Annotation]  # No changes in file, keep verbatim
    shift: list[Annotation]  # Not overlapping, but need line shift
    regenerate: list[Annotation]  # Overlapping a hunk, needs LLM


def classify_annotations(
    annotations: list[Annotation],
    file_hunks: dict[str, FileHunks],
) -> ClassifiedAnnotations:
    """Classify existing annotations against changed hunks.

    For files not in the diff: keep annotations verbatim.
    For files in the diff: check each annotation against hunks.
    """
    keep: list[Annotation] = []
    shift: list[Annotation] = []
    regenerate: list[Annotation] = []

    for ann in annotations:
        if ann.file not in file_hunks:
            keep.append(ann)
            continue

        hunks = file_hunks[ann.file].hunks
        overlaps = False
        needs_shift = False

        for hunk in hunks:
            # The hunk's old range (what the annotation's lines refer to)
            hunk_old_end = hunk.old_start + hunk.old_count - 1
            if hunk.old_count == 0:
                # Pure insertion — affects annotations at or after the insertion point
                if ann.start_line >= hunk.old_start:
                    needs_shift = True
                continue

            # Check overlap between annotation range and hunk's old range
            if ann.start_line <= hunk_old_end and ann.end_line >= hunk.old_start:
                overlaps = True
                break

            # Annotation is entirely below this hunk
            if ann.start_line > hunk_old_end:
                needs_shift = True

        if overlaps:
            regenerate.append(ann)
        elif needs_shift:
            shift.append(ann)
        else:
            keep.append(ann)

    return ClassifiedAnnotations(keep=keep, shift=shift, regenerate=regenerate)


def shift_annotations(
    annotations: list[Annotation],
    file_hunks: dict[str, FileHunks],
) -> list[Annotation]:
    """Mechanically shift annotation line numbers based on diff deltas.

    For each file, compute the cumulative line offset from hunks that appear
    before each annotation, then adjust start_line and end_line.
    """
    shifted: list[Annotation] = []

    for ann in annotations:
        if ann.file not in file_hunks:
            shifted.append(ann)
            continue

        hunks = sorted(file_hunks[ann.file].hunks, key=lambda h: h.old_start)
        cumulative_delta = 0

        for hunk in hunks:
            hunk_old_end = hunk.old_start + max(hunk.old_count - 1, 0)
            # Only count hunks that are entirely before this annotation
            if hunk_old_end < ann.start_line:
                cumulative_delta += hunk.delta

        new_start = ann.start_line + cumulative_delta
        new_end = ann.end_line + cumulative_delta

        # Clamp to valid range
        new_start = max(1, new_start)
        new_end = max(new_start, new_end)

        shifted.append(ann.model_copy(update={
            "start_line": new_start,
            "end_line": new_end,
        }))

    return shifted
