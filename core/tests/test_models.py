"""Tests for Pydantic model serialization/deserialization."""

from __future__ import annotations

import json

from specmap.state.models import (
    Annotation,
    SpecmapFile,
    SpecRef,
    _generate_annotation_id,
)


def test_annotation_id_format():
    """Generated annotation ID should start with a_ and have 12 hex chars."""
    aid = _generate_annotation_id()
    assert aid.startswith("a_")
    assert len(aid) == 14  # "a_" + 12 chars


def test_annotation_id_uniqueness():
    """Generated IDs should be unique."""
    ids = {_generate_annotation_id() for _ in range(100)}
    assert len(ids) == 100


def test_specmap_file_round_trip(sample_specmap: SpecmapFile):
    """Serialize to JSON and back should produce equivalent model."""
    json_str = sample_specmap.model_dump_json()
    restored = SpecmapFile.model_validate_json(json_str)

    assert restored.version == sample_specmap.version
    assert restored.branch == sample_specmap.branch
    assert restored.base_branch == sample_specmap.base_branch
    assert restored.head_sha == sample_specmap.head_sha
    assert len(restored.annotations) == len(sample_specmap.annotations)


def test_specmap_file_json_structure(sample_specmap: SpecmapFile):
    """JSON output should have expected top-level keys."""
    data = json.loads(sample_specmap.model_dump_json())
    assert "version" in data
    assert "branch" in data
    assert "base_branch" in data
    assert "head_sha" in data
    assert "updated_at" in data
    assert "updated_by" in data
    assert "annotations" in data
    assert "ignore_patterns" in data


def test_annotation_defaults():
    """Annotation should have sensible defaults."""
    a = Annotation(
        file="test.go",
        start_line=1,
        end_line=10,
        description="Test annotation",
    )
    assert a.id.startswith("a_")
    assert a.refs == []
    assert a.created_at is not None


def test_spec_ref_fields():
    """SpecRef should serialize all fields."""
    ref = SpecRef(
        id=1,
        spec_file="test.md",
        heading="Token Storage",
        start_line=5,
        excerpt="Tokens are stored securely.",
    )
    data = json.loads(ref.model_dump_json())
    assert data["id"] == 1
    assert data["spec_file"] == "test.md"
    assert data["heading"] == "Token Storage"
    assert data["start_line"] == 5
    assert data["excerpt"] == "Tokens are stored securely."


def test_specmap_file_empty():
    """Empty SpecmapFile should serialize/deserialize cleanly."""
    sf = SpecmapFile()
    json_str = sf.model_dump_json()
    restored = SpecmapFile.model_validate_json(json_str)
    assert restored.version == 2
    assert restored.annotations == []
    assert restored.head_sha == ""


def test_annotation_with_refs():
    """Annotation with refs should round-trip."""
    ann = Annotation(
        file="src/main.go",
        start_line=1,
        end_line=20,
        description="Implements auth with AES-256. [1]",
        refs=[
            SpecRef(
                id=1,
                spec_file="docs/spec.md",
                heading="Authentication > Encryption",
                start_line=10,
                excerpt="All tokens are encrypted at rest using AES-256-GCM.",
            ),
        ],
    )
    json_str = ann.model_dump_json()
    restored = Annotation.model_validate_json(json_str)
    assert len(restored.refs) == 1
    assert restored.refs[0].heading == "Authentication > Encryption"
    assert restored.description == "Implements auth with AES-256. [1]"
