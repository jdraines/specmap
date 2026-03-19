"""Tests for specmap.indexer.validator — port of Go validator_test.go."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from specmap.indexer.hasher import hash_code_lines, hash_content
from specmap.indexer.validator import validate_specmap
from specmap.state.models import (
    CodeTarget,
    Mapping,
    SpecDocument,
    SpecmapFile,
    SpecSection,
    SpecSpan,
)


SAMPLE_SPEC = """\
# Authentication

This document describes the authentication system.

## Token Storage

Tokens are stored securely in the session store. Each token has a TTL
of 24 hours and is refreshed on activity.

### Encryption

All tokens are encrypted at rest using AES-256-GCM.

## Session Management

Sessions track user activity and expire after inactivity.
"""

SAMPLE_CODE = """\
package auth

import "time"

// SessionStore manages authentication tokens.
type SessionStore struct {
    tokens map[string]*Token
    ttl    time.Duration
}

// NewSessionStore creates a new session store with a 24h TTL.
func NewSessionStore() *SessionStore {
    return &SessionStore{
        tokens: make(map[string]*Token),
        ttl:    24 * time.Hour,
    }
}"""


def _make_specmap(
    tmp_path: Path,
    spec_content: str = SAMPLE_SPEC,
    code_content: str = SAMPLE_CODE,
    spec_path: str = "docs/auth-spec.md",
    code_path: str = "src/auth.go",
    code_start: int = 1,
    code_end: int = 17,
) -> tuple[SpecmapFile, str]:
    """Create a specmap file with correct hashes from actual file content."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Write files.
    (repo / spec_path).parent.mkdir(parents=True, exist_ok=True)
    (repo / spec_path).write_text(spec_content, encoding="utf-8")
    (repo / code_path).parent.mkdir(parents=True, exist_ok=True)
    (repo / code_path).write_text(code_content, encoding="utf-8")

    # Compute hashes.
    doc_hash = hash_content(spec_content)
    code_hash = hash_code_lines(code_content, code_start, code_end)

    # Build a span from the Token Storage heading.
    span_start = spec_content.index("## Token Storage")
    span_end = spec_content.index("### Encryption")
    span_text = spec_content[span_start:span_end]
    span_hash = hash_content(span_text)

    sf = SpecmapFile(
        version=1,
        branch="feature/test",
        base_branch="main",
        spec_documents={
            spec_path: SpecDocument(
                doc_hash=doc_hash,
                sections={
                    "Authentication > Token Storage": SpecSection(
                        heading_path=["Authentication", "Token Storage"],
                        heading_line=5,
                        section_hash="sha256:0000000000000000",
                    ),
                },
            ),
        },
        mappings=[
            Mapping(
                id="m_test001",
                spec_spans=[
                    SpecSpan(
                        spec_file=spec_path,
                        heading_path=["Authentication", "Token Storage"],
                        span_offset=span_start,
                        span_length=span_end - span_start,
                        span_hash=span_hash,
                        relevance=0.95,
                    ),
                ],
                code_target=CodeTarget(
                    file=code_path,
                    start_line=code_start,
                    end_line=code_end,
                    content_hash=code_hash,
                ),
                stale=False,
                created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
            ),
        ],
    )
    return sf, str(repo)


class TestHashContent:
    def test_format(self):
        h = hash_content("hello world")
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 16

    def test_consistency(self):
        assert hash_content("test") == hash_content("test")

    def test_no_collision(self):
        assert hash_content("aaa") != hash_content("bbb")


class TestValidateValidHashes:
    def test_all_valid(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        results = validate_specmap(sf, repo_root)
        assert all(r.valid for r in results), [r.message for r in results if not r.valid]
        assert len(results) >= 3  # doc + code + span


class TestValidateInvalidDocHash:
    def test_wrong_doc_hash(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        sf.spec_documents["docs/auth-spec.md"].doc_hash = "sha256:0000000000000000"
        results = validate_specmap(sf, repo_root)
        doc_results = [r for r in results if not r.lines and r.file == "docs/auth-spec.md"]
        assert any(not r.valid and "mismatch" in r.message for r in doc_results)


class TestValidateInvalidCodeHash:
    def test_wrong_code_hash(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        sf.mappings[0].code_target.content_hash = "sha256:0000000000000000"
        results = validate_specmap(sf, repo_root)
        code_results = [r for r in results if r.lines]
        assert any(not r.valid and "mismatch" in r.message for r in code_results)


class TestValidateMissingFile:
    def test_missing_spec(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        (Path(repo_root) / "docs" / "auth-spec.md").unlink()
        results = validate_specmap(sf, repo_root)
        assert any(not r.valid and "cannot read" in r.message for r in results)

    def test_missing_code(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        (Path(repo_root) / "src" / "auth.go").unlink()
        results = validate_specmap(sf, repo_root)
        assert any(not r.valid and "cannot read" in r.message for r in results)


class TestCodeHashNormalization:
    def test_trailing_newline_stripped(self, tmp_path):
        """Code with trailing newline should hash the same as without."""
        code_with_newline = SAMPLE_CODE + "\n"
        sf, repo_root = _make_specmap(tmp_path, code_content=code_with_newline)
        results = validate_specmap(sf, repo_root)
        code_results = [r for r in results if r.lines]
        assert all(r.valid for r in code_results), [r.message for r in code_results]


class TestValidateLineRangeOutOfBounds:
    def test_out_of_bounds(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        sf.mappings[0].code_target.start_line = 1
        sf.mappings[0].code_target.end_line = 999
        results = validate_specmap(sf, repo_root)
        code_results = [r for r in results if r.lines]
        assert any(not r.valid and "out of bounds" in r.message for r in code_results)
