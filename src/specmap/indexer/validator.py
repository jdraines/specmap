"""Validation for specmap annotation files — checks code line ranges exist."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specmap.state.models import SpecmapFile


@dataclass
class ValidateResult:
    """Per-item validation result."""

    valid: bool
    message: str
    file: str
    lines: str = ""  # "15-42" for annotations


def validate_specmap(sf: SpecmapFile, repo_root: str) -> list[ValidateResult]:
    """Validate all annotations in a SpecmapFile against actual file contents.

    Checks that annotated line ranges are within bounds for each code file.
    """
    results: list[ValidateResult] = []
    root = Path(repo_root)

    for ann in sf.annotations:
        abs_path = root / ann.file
        try:
            data = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            results.append(ValidateResult(
                valid=False,
                message=f"cannot read file: {e}",
                file=ann.file,
                lines=f"{ann.start_line}-{ann.end_line}",
            ))
            continue

        lines = data.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]

        line_range = f"{ann.start_line}-{ann.end_line}"

        if ann.start_line < 1 or ann.end_line > len(lines) or ann.start_line > ann.end_line:
            results.append(ValidateResult(
                valid=False,
                message=(
                    f"line range {ann.start_line}-{ann.end_line} out of bounds "
                    f"(file has {len(lines)} lines)"
                ),
                file=ann.file,
                lines=line_range,
            ))
            continue

        results.append(ValidateResult(
            valid=True,
            message="line range OK",
            file=ann.file,
            lines=line_range,
        ))

    return results
