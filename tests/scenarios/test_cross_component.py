"""H. Cross-component — Python writes -> Go reads, full lifecycle, hash compat."""

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
    assert_check_json_pass,
)
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.annotate import annotate
from specmap.tools.check_sync import check_sync
from specmap.tools.get_unmapped import get_unmapped_changes
from specmap.indexer.hasher import hash_content, hash_code, hash_code_lines
from specmap.llm.schemas import AnnotationResponse

from conftest import setup_spec_on_main


# ── H29: Full lifecycle — annotate -> check -> unmapped ──────────────────────

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

    # Step 2: Check (CLI)
    chk = cli_runner.check(repo, "feature/test", base="main")
    assert_check_json_pass(chk)

    # Step 3: Get unmapped
    unmapped = await get_unmapped_changes(str(repo.path), branch="feature/test")
    assert unmapped["overall_coverage"] == 1.0

    # Step 4: check_sync verifies line ranges
    sync = await check_sync(str(repo.path), branch="feature/test")
    assert sync["valid"] >= 1
    assert sync["invalid"] == 0

    # Step 5: Validate — final state should be valid
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── H30: Python writes, CLI reads ───────────────────────────────────────────

async def test_python_writes_cli_reads(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    """Python annotate writes .specmap JSON, CLI validates and checks."""
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

    # CLI check: reads Python-written JSON, computes coverage
    chk = cli_runner.check(repo, "feature/test", base="main")
    assert_check_json_pass(chk)
    assert chk.json_data["coverage"] == 1.0


# ── H31: CLI --json output schema ───────────────────────────────────────────

async def test_cli_json_schema(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add code")

    ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[ann]))
    await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )

    chk = cli_runner.check(repo, "feature/test", base="main")
    data = chk.json_data
    assert data is not None, f"No JSON output; stdout={chk.stdout}"

    # All expected keys present
    expected_keys = {
        "branch", "base_branch", "total_files", "mapped_files",
        "total_lines", "mapped_lines", "coverage", "threshold",
        "pass", "unmapped",
    }
    missing = expected_keys - set(data.keys())
    assert not missing, f"Missing keys in check JSON: {missing}"

    # Type checks
    assert isinstance(data["coverage"], (int, float))
    assert isinstance(data["pass"], bool)
    assert isinstance(data["unmapped"], list)


# ── H32: Code hash compatibility between Python and Go ──────────────────────

def test_code_hash_compatibility(scenario_repo: GitRepo, cli_runner: CLIRunner):
    """Verify Python and Go produce identical code-target hashes.

    Both sides normalize code content before hashing:
      - Python: hash_code / hash_code_lines strip trailing newlines
      - Go: strings.Split + strings.Join naturally drops trailing newlines
    """
    repo = scenario_repo

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
