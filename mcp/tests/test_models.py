"""Tests for Pydantic model serialization/deserialization."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from specmap_mcp.state.models import (
    CodeTarget,
    Mapping,
    SpecDocument,
    SpecmapFile,
    SpecSection,
    SpecSpan,
    _generate_mapping_id,
)


def test_mapping_id_format():
    """Generated mapping ID should start with m_ and have 12 hex chars."""
    mid = _generate_mapping_id()
    assert mid.startswith("m_")
    assert len(mid) == 14  # "m_" + 12 chars


def test_mapping_id_uniqueness():
    """Generated IDs should be unique."""
    ids = {_generate_mapping_id() for _ in range(100)}
    assert len(ids) == 100


def test_specmap_file_round_trip(sample_specmap: SpecmapFile):
    """Serialize to JSON and back should produce equivalent model."""
    json_str = sample_specmap.model_dump_json()
    restored = SpecmapFile.model_validate_json(json_str)

    assert restored.version == sample_specmap.version
    assert restored.branch == sample_specmap.branch
    assert restored.base_branch == sample_specmap.base_branch
    assert len(restored.mappings) == len(sample_specmap.mappings)
    assert len(restored.spec_documents) == len(sample_specmap.spec_documents)


def test_specmap_file_json_structure(sample_specmap: SpecmapFile):
    """JSON output should have expected top-level keys."""
    data = json.loads(sample_specmap.model_dump_json())
    assert "version" in data
    assert "branch" in data
    assert "base_branch" in data
    assert "updated_at" in data
    assert "updated_by" in data
    assert "spec_documents" in data
    assert "mappings" in data
    assert "ignore_patterns" in data


def test_mapping_defaults():
    """Mapping should have sensible defaults."""
    m = Mapping(
        code_target=CodeTarget(
            file="test.go",
            start_line=1,
            end_line=10,
            content_hash="sha256:abcdef0123456789",
        ),
    )
    assert m.id.startswith("m_")
    assert m.stale is False
    assert m.spec_spans == []
    assert m.created_at is not None


def test_spec_span_relevance_bounds():
    """SpecSpan relevance should be between 0 and 1."""
    span = SpecSpan(
        spec_file="test.md",
        heading_path=["A"],
        span_offset=0,
        span_length=10,
        span_hash="sha256:0000000000000000",
        relevance=0.5,
    )
    assert span.relevance == 0.5


def test_specmap_file_empty():
    """Empty SpecmapFile should serialize/deserialize cleanly."""
    sf = SpecmapFile()
    json_str = sf.model_dump_json()
    restored = SpecmapFile.model_validate_json(json_str)
    assert restored.version == 1
    assert restored.mappings == []
    assert restored.spec_documents == {}


def test_spec_document_sections():
    """SpecDocument with sections should round-trip."""
    doc = SpecDocument(
        doc_hash="sha256:abcdef0123456789",
        sections={
            "A > B": SpecSection(
                heading_path=["A", "B"],
                heading_line=10,
                section_hash="sha256:1234567890abcdef",
            ),
        },
    )
    json_str = doc.model_dump_json()
    restored = SpecDocument.model_validate_json(json_str)
    assert "A > B" in restored.sections
    assert restored.sections["A > B"].heading_path == ["A", "B"]
