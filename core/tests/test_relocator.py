"""Tests for span relocation."""

from __future__ import annotations

from specmap.indexer.hasher import hash_span
from specmap.state.models import CodeTarget, Mapping, SpecSpan
from specmap.state.relocator import Relocator


def _make_span(spec_file: str, offset: int, length: int, content: str) -> SpecSpan:
    """Helper to create a SpecSpan with proper hash."""
    return SpecSpan(
        spec_file=spec_file,
        heading_path=["Test"],
        span_offset=offset,
        span_length=length,
        span_hash=hash_span(content, offset, length),
    )


def test_relocate_exact_same_position():
    """Span found at exact same offset in new content."""
    relocator = Relocator()
    old_content = "Hello, this is the target text, followed by more."
    new_content = "Hello, this is the target text, followed by more."

    span = _make_span("test.md", 7, 24, old_content)
    result = relocator.relocate_span(span, old_content, new_content)

    assert result is not None
    assert result.span_offset == 7
    assert result.span_length == 24


def test_relocate_exact_match_moved():
    """Span text moved to a different offset."""
    relocator = Relocator()
    old_content = "prefix: the target text here."
    new_content = "new prefix added, the target text here."

    span = _make_span("test.md", 8, 15, old_content)  # "the target text"
    result = relocator.relocate_span(span, old_content, new_content)

    assert result is not None
    assert result.span_offset == new_content.index("the target text")
    assert result.span_length == 15


def test_relocate_fuzzy_match():
    """Span text slightly changed, should fuzzy-match."""
    relocator = Relocator()
    old_content = "Tokens are stored securely in the session store."
    new_content = "Tokens are stored safely in the session store."

    # "stored securely in the session" -> "stored safely in the session"
    span = _make_span("test.md", 11, 30, old_content)  # "stored securely in the session"
    result = relocator.relocate_span(span, old_content, new_content)

    # Should find a fuzzy match
    assert result is not None


def test_relocate_failure():
    """Span text completely gone, relocation should fail."""
    relocator = Relocator()
    old_content = "The quick brown fox jumps over the lazy dog."
    new_content = "Completely different content with no similarity at all."

    span = _make_span("test.md", 4, 15, old_content)  # "quick brown fox"
    result = relocator.relocate_span(span, old_content, new_content)

    assert result is None


def test_relocate_mappings_split():
    """relocate_mappings should separate relocated from stale."""
    relocator = Relocator()

    old_a = "First target text here, this is a unique passage that should be findable."
    new_a = "First target text here, this is a unique passage that should be findable."
    old_b = "The quantum flux capacitor generates temporal vortex resonance harmonics."
    new_b = "Completely replaced with 1234567890 xyzzy plugh nothing alike at all here."

    span1 = _make_span("a.md", 0, len(old_a), old_a)  # still exists
    span2 = _make_span("b.md", 0, len(old_b), old_b)  # gone

    m1 = Mapping(
        id="m_test1",
        spec_spans=[span1],
        code_target=CodeTarget(
            file="test.go", start_line=1, end_line=5, content_hash="sha256:0000000000000000"
        ),
    )
    m2 = Mapping(
        id="m_test2",
        spec_spans=[span2],
        code_target=CodeTarget(
            file="test.go", start_line=10, end_line=15, content_hash="sha256:1111111111111111"
        ),
    )

    relocated, stale = relocator.relocate_mappings(
        [m1, m2],
        {"a.md": old_a, "b.md": old_b},
        {"a.md": new_a, "b.md": new_b},
    )

    assert len(relocated) == 1
    assert relocated[0].id == "m_test1"
    assert len(stale) == 1
    assert stale[0].id == "m_test2"
    assert stale[0].stale is True


def test_relocate_empty_span():
    """Empty span text should fail relocation."""
    relocator = Relocator()
    span = SpecSpan(
        spec_file="test.md",
        heading_path=["Test"],
        span_offset=0,
        span_length=0,
        span_hash="sha256:0000000000000000",
    )
    result = relocator.relocate_span(span, "content", "content")
    assert result is None
