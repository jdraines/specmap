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


def hash_code(content: str) -> str:
    """Hash a region of code."""
    return hash_content(content)


def hash_code_lines(file_content: str, start_line: int, end_line: int) -> str:
    """Extract lines from file content (1-based) and hash them."""
    lines = file_content.splitlines(keepends=True)
    # Convert to 0-based indexing, end_line is inclusive
    selected = lines[start_line - 1 : end_line]
    return hash_content("".join(selected))
