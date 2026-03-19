"""Hash validation for specmap files — port of Go validator.go."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specmap.indexer.hasher import hash_code_lines, hash_content
from specmap.state.models import SpecmapFile


@dataclass
class ValidateResult:
    """Per-item validation result."""

    valid: bool
    message: str
    file: str
    lines: str = ""  # "15-42" for code targets, empty for docs


def validate_specmap(sf: SpecmapFile, repo_root: str) -> list[ValidateResult]:
    """Validate all hashes in a SpecmapFile against actual file contents.

    Checks:
    - doc_hash for each spec document
    - content_hash for each code target
    - span_hash for each spec span
    """
    results: list[ValidateResult] = []
    root = Path(repo_root)

    # Validate spec documents.
    for doc_path, doc in sf.spec_documents.items():
        abs_path = root / doc_path
        try:
            data = abs_path.read_bytes()
        except OSError as e:
            results.append(ValidateResult(
                valid=False,
                message=f"cannot read file: {e}",
                file=doc_path,
            ))
            continue

        actual_hash = hash_content(data.decode("utf-8"))
        if actual_hash == doc.doc_hash:
            results.append(ValidateResult(valid=True, message="hash OK", file=doc_path))
        else:
            results.append(ValidateResult(
                valid=False,
                message=f"hash mismatch (expected {doc.doc_hash}, got {actual_hash})",
                file=doc_path,
            ))

    # Validate mappings.
    for m in sf.mappings:
        ct = m.code_target
        abs_path = root / ct.file
        try:
            data = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            results.append(ValidateResult(
                valid=False,
                message=f"cannot read file: {e}",
                file=ct.file,
                lines=f"{ct.start_line}-{ct.end_line}",
            ))
            continue

        lines = data.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]

        if ct.start_line < 1 or ct.end_line > len(lines) or ct.start_line > ct.end_line:
            results.append(ValidateResult(
                valid=False,
                message=(
                    f"line range {ct.start_line}-{ct.end_line} out of bounds "
                    f"(file has {len(lines)} lines)"
                ),
                file=ct.file,
                lines=f"{ct.start_line}-{ct.end_line}",
            ))
            continue

        actual_hash = hash_code_lines(data, ct.start_line, ct.end_line)
        line_range = f"{ct.start_line}-{ct.end_line}"
        if actual_hash == ct.content_hash:
            results.append(ValidateResult(
                valid=True, message="hash OK", file=ct.file, lines=line_range,
            ))
        else:
            results.append(ValidateResult(
                valid=False,
                message=f"hash mismatch (expected {ct.content_hash}, got {actual_hash})",
                file=ct.file,
                lines=line_range,
            ))

        # Validate spec span hashes.
        for span in m.spec_spans:
            spec_abs = root / span.spec_file
            try:
                spec_data = spec_abs.read_text(encoding="utf-8")
            except OSError as e:
                results.append(ValidateResult(
                    valid=False,
                    message=f"cannot read spec file: {e}",
                    file=span.spec_file,
                ))
                continue

            if span.span_offset < 0 or span.span_offset + span.span_length > len(spec_data):
                results.append(ValidateResult(
                    valid=False,
                    message=(
                        f"span offset {span.span_offset}+{span.span_length} out of bounds "
                        f"(file length {len(spec_data)})"
                    ),
                    file=span.spec_file,
                ))
                continue

            span_text = spec_data[span.span_offset : span.span_offset + span.span_length]
            span_actual = hash_content(span_text)
            if span_actual == span.span_hash:
                results.append(ValidateResult(
                    valid=True, message="span hash OK", file=span.spec_file,
                ))
            else:
                results.append(ValidateResult(
                    valid=False,
                    message=(
                        f"span hash mismatch (expected {span.span_hash}, got {span_actual})"
                    ),
                    file=span.spec_file,
                ))

    return results
