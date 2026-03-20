"""H. Cross-component — Python writes -> CLI reads, full lifecycle, hash compat."""

from __future__ import annotations

import json

import pytest

from harness.spec_content import AUTH_SPEC
from harness.code_content import AUTH_GO
from harness.llm_mock import build_annotation_for_spec, LLMMockRegistry
from harness.assertions import (
    assert_annotate_ok,
    assert_pass,
    assert_fail,
    assert_all_valid,
)
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.annotate import annotate
from specmap.tools.check_sync import check_sync
from specmap.indexer.hasher import hash_content, hash_code, hash_code_lines
from specmap.llm.schemas import AnnotationResponse

from conftest import setup_spec_on_main


# ── H29: Full lifecycle — annotate -> check_sync -> validate ──────────────────

async def test_full_lifecycle(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth code")

    # Step 1: Annotate
    ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[ann]))
    annotate_result = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(annotate_result)

    # Step 2: check_sync verifies line ranges
    sync = await check_sync(str(repo.path), branch="feature/test")
    assert sync["valid"] >= 1
    assert sync["invalid"] == 0

    # Step 3: Validate — final state should be valid
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── H30: Python writes, CLI reads ───────────────────────────────────────────

async def test_python_writes_cli_reads(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    """Python annotate writes .specmap JSON, CLI validates."""
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth code")

    ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[ann]))
    result = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(result)

    # CLI validate: reads Python-written JSON, verifies line ranges
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── H32: Code hash compatibility between Python and Go ──────────────────────

def test_code_hash_compatibility(scenario_repo: GitRepo):
    """Verify Python and Go produce identical code-target hashes.

    Both sides normalize code content before hashing:
      - Python: hash_code / hash_code_lines strip trailing newlines
      - Go: strings.Split + strings.Join naturally drops trailing newlines
    """
    def _simulate_go_hash(content: str, end_line: int) -> str:
        """Reproduce Go's line extraction: Split → select → Join → Hash."""
        lines = content.split("\n")
        selected = lines[0:end_line]
        return hash_content("\n".join(selected))

    # --- Case 1: file WITHOUT trailing newline ---
    content_no_trail = "line1\nline2\nline3"
    n = len(content_no_trail.splitlines())  # 3

    py_hash = hash_code_lines(content_no_trail, 1, n)
    go_hash = _simulate_go_hash(content_no_trail, n)
    assert py_hash == go_hash, "Hashes should match (no trailing newline)"

    # --- Case 2: file WITH trailing newline ---
    content_trail = "line1\nline2\nline3\n"
    n_trail = len(content_trail.splitlines())  # still 3

    py_hash_trail = hash_code_lines(content_trail, 1, n_trail)
    go_hash_trail = _simulate_go_hash(content_trail, n_trail)
    assert py_hash_trail == go_hash_trail, (
        "Hashes should match even with trailing newline (both sides normalize)"
    )

    # --- Case 3: hash_code on full content also matches ---
    assert hash_code(content_trail) == hash_code(content_no_trail), (
        "hash_code normalizes trailing newlines"
    )
    assert hash_code(content_trail) == go_hash_trail
