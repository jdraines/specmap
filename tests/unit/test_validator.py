"""Tests for specmap.indexer.validator — annotation line range validation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from specmap.indexer.validator import validate_specmap
from specmap.state.models import (
    Annotation,
    SpecmapFile,
    SpecRef,
)


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
    code_content: str = SAMPLE_CODE,
    code_path: str = "src/auth.go",
    code_start: int = 1,
    code_end: int = 17,
) -> tuple[SpecmapFile, str]:
    """Create a specmap file with annotations matching actual file content."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Write code file
    (repo / code_path).parent.mkdir(parents=True, exist_ok=True)
    (repo / code_path).write_text(code_content, encoding="utf-8")

    sf = SpecmapFile(
        version=2,
        branch="feature/test",
        base_branch="main",
        annotations=[
            Annotation(
                id="a_test001",
                file=code_path,
                start_line=code_start,
                end_line=code_end,
                description="Implements session store with 24h TTL. [1]",
                refs=[
                    SpecRef(
                        id=1,
                        spec_file="docs/auth-spec.md",
                        heading="Token Storage",
                        start_line=6,
                        excerpt="Tokens are stored securely in the session store.",
                    ),
                ],
                created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
            ),
        ],
    )
    return sf, str(repo)


class TestValidateValidRanges:
    def test_all_valid(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        results = validate_specmap(sf, repo_root)
        assert all(r.valid for r in results), [r.message for r in results if not r.valid]
        assert len(results) == 1


class TestValidateMissingFile:
    def test_missing_code(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        (Path(repo_root) / "src" / "auth.go").unlink()
        results = validate_specmap(sf, repo_root)
        assert any(not r.valid and "cannot read" in r.message for r in results)


class TestValidateLineRangeOutOfBounds:
    def test_out_of_bounds(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        sf.annotations[0].start_line = 1
        sf.annotations[0].end_line = 999
        results = validate_specmap(sf, repo_root)
        assert any(not r.valid and "out of bounds" in r.message for r in results)

    def test_invalid_range(self, tmp_path):
        sf, repo_root = _make_specmap(tmp_path)
        sf.annotations[0].start_line = 10
        sf.annotations[0].end_line = 5  # end < start
        results = validate_specmap(sf, repo_root)
        assert any(not r.valid and "out of bounds" in r.message for r in results)
