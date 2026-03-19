"""Tests for the hashing functions."""

from __future__ import annotations

import re

from specmap_mcp.indexer.hasher import (
    hash_code,
    hash_code_lines,
    hash_content,
    hash_document,
    hash_section,
    hash_span,
)


_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{16}$")


def test_hash_content_format():
    """Hash should be sha256: prefix + 16 hex chars."""
    result = hash_content("hello world")
    assert _HASH_PATTERN.match(result), f"Bad format: {result}"


def test_hash_content_deterministic():
    """Same input should produce same hash."""
    assert hash_content("test") == hash_content("test")


def test_hash_content_different_inputs():
    """Different inputs should produce different hashes."""
    assert hash_content("hello") != hash_content("world")


def test_hash_document():
    """hash_document should return correct format."""
    result = hash_document("# Heading\n\nSome content.")
    assert _HASH_PATTERN.match(result)


def test_hash_section():
    """hash_section should return correct format."""
    result = hash_section("## Section\n\nSection content.")
    assert _HASH_PATTERN.match(result)


def test_hash_span():
    """hash_span should hash the extracted span."""
    text = "Hello, this is a test document."
    result = hash_span(text, 7, 4)  # "this"
    expected = hash_content("this")
    assert result == expected
    assert _HASH_PATTERN.match(result)


def test_hash_span_full_text():
    """hash_span with full text range."""
    text = "complete"
    result = hash_span(text, 0, len(text))
    expected = hash_content(text)
    assert result == expected


def test_hash_code():
    """hash_code should return correct format."""
    result = hash_code("func main() {}")
    assert _HASH_PATTERN.match(result)


def test_hash_code_lines():
    """hash_code_lines extracts the right lines (1-based) and hashes them."""
    content = "line1\nline2\nline3\nline4\nline5\n"
    result = hash_code_lines(content, 2, 4)
    expected = hash_content("line2\nline3\nline4\n")
    assert result == expected
    assert _HASH_PATTERN.match(result)


def test_hash_code_lines_single_line():
    """hash_code_lines with a single line."""
    content = "first\nsecond\nthird\n"
    result = hash_code_lines(content, 2, 2)
    expected = hash_content("second\n")
    assert result == expected


def test_hash_empty_string():
    """Hashing empty string should still return valid format."""
    result = hash_content("")
    assert _HASH_PATTERN.match(result)
