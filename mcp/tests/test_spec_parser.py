"""Tests for the spec parser."""

from __future__ import annotations

import re

from specmap_mcp.indexer.spec_parser import SpecParser


_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{16}$")


NESTED_MARKDOWN = """\
# Top Level

Intro text.

## Second Level A

Content A.

### Third Level A1

Content A1.

### Third Level A2

Content A2.

## Second Level B

Content B.
"""


def test_parse_returns_spec_document():
    """Parser should return a SpecDocument with doc_hash."""
    parser = SpecParser()
    doc = parser.parse(NESTED_MARKDOWN, "test.md")
    assert _HASH_PATTERN.match(doc.doc_hash)


def test_parse_finds_all_sections():
    """Parser should find all 5 headings/sections."""
    parser = SpecParser()
    doc = parser.parse(NESTED_MARKDOWN, "test.md")
    assert len(doc.sections) == 5


def test_parse_section_keys():
    """Section keys should use ' > ' separator."""
    parser = SpecParser()
    doc = parser.parse(NESTED_MARKDOWN, "test.md")
    keys = set(doc.sections.keys())
    assert "Top Level" in keys
    assert "Top Level > Second Level A" in keys
    assert "Top Level > Second Level A > Third Level A1" in keys
    assert "Top Level > Second Level A > Third Level A2" in keys
    assert "Top Level > Second Level B" in keys


def test_parse_heading_paths():
    """Each section should have correct heading_path list."""
    parser = SpecParser()
    doc = parser.parse(NESTED_MARKDOWN, "test.md")

    section = doc.sections["Top Level > Second Level A > Third Level A1"]
    assert section.heading_path == ["Top Level", "Second Level A", "Third Level A1"]


def test_parse_heading_lines():
    """heading_line should be 1-based line number."""
    parser = SpecParser()
    doc = parser.parse(NESTED_MARKDOWN, "test.md")

    # "# Top Level" is line 1
    assert doc.sections["Top Level"].heading_line == 1
    # "## Second Level A" is line 5
    assert doc.sections["Top Level > Second Level A"].heading_line == 5


def test_parse_section_hashes():
    """Each section should have a valid section_hash."""
    parser = SpecParser()
    doc = parser.parse(NESTED_MARKDOWN, "test.md")

    for section in doc.sections.values():
        assert _HASH_PATTERN.match(section.section_hash)


def test_parse_empty_document():
    """Parsing empty content should return empty sections."""
    parser = SpecParser()
    doc = parser.parse("", "empty.md")
    assert doc.sections == {}
    assert _HASH_PATTERN.match(doc.doc_hash)


def test_parse_no_headings():
    """Parsing document with no headings returns empty sections."""
    parser = SpecParser()
    doc = parser.parse("Just some text.\nMore text.", "plain.md")
    assert doc.sections == {}


def test_parse_single_heading():
    """Parsing document with single heading."""
    parser = SpecParser()
    doc = parser.parse("# Only Heading\n\nSome content.", "single.md")
    assert len(doc.sections) == 1
    assert "Only Heading" in doc.sections
    assert doc.sections["Only Heading"].heading_line == 1
