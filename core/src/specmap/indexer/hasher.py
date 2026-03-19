"""Hierarchical hashing functions for Specmap.

All SHA-256, truncated to 16 hex chars, prefixed with "sha256:".
"""

from __future__ import annotations

import hashlib


def hash_content(content: str) -> str:
    """Base hash function: SHA-256 of content, truncated to 16 hex chars."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest}"


def hash_document(content: str) -> str:
    """Hash an entire document's content."""
    return hash_content(content)


def hash_section(content: str) -> str:
    """Hash a section of a document (content under a heading)."""
    return hash_content(content)


def hash_span(text: str, offset: int, length: int) -> str:
    """Hash a specific span of text extracted by offset and length."""
    span_text = text[offset : offset + length]
    return hash_content(span_text)


def _normalize_code(content: str) -> str:
    """Normalize code content for hashing.

    Strips trailing newlines so that Python and Go produce identical hashes.
    Go's ``strings.Split(content, "\\n")`` + ``strings.Join(lines, "\\n")``
    naturally drops trailing newlines; this function matches that behavior.
    """
    return content.rstrip("\n")


def hash_code(content: str) -> str:
    """Hash a region of code (trailing newlines stripped for cross-language consistency)."""
    return hash_content(_normalize_code(content))


def hash_code_lines(file_content: str, start_line: int, end_line: int) -> str:
    """Extract lines from file content (1-based, inclusive) and hash them.

    Uses split("\\n") and join("\\n") to match Go's line-extraction semantics,
    ensuring hashes are identical across Python and Go.
    """
    lines = file_content.split("\n")
    # Drop trailing empty element produced by a final newline
    if lines and lines[-1] == "":
        lines = lines[:-1]
    selected = lines[start_line - 1 : end_line]
    return hash_content("\n".join(selected))
