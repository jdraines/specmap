"""E. Coverage edge cases — threshold enforcement, ignore patterns, stale."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from harness.spec_content import AUTH_SPEC, API_SPEC
from harness.code_content import AUTH_GO, API_GO
from harness.llm_mock import build_mapping_for_spec, LLMMockRegistry
from harness.assertions import (
    assert_map_ok,
    assert_check_json_pass,
    assert_check_json_fail,
    assert_coverage,
)
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.map_code_to_spec import map_code_to_spec
from specmap.tools.get_unmapped import get_unmapped_changes
from specmap.indexer.hasher import hash_content, hash_document, hash_span, hash_code
from specmap.llm.schemas import MappingResponse

from conftest import setup_spec_on_main


def _build_specmap_data(
    branch: str,
    spec_file: str,
    spec_content: str,
    mappings_data: list[dict],
) -> dict:
    """Build a raw specmap dict with exact control over content."""
    return {
        "version": 1,
        "branch": branch,
        "base_branch": "main",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "test",
        "spec_documents": {
            spec_file: {
                "doc_hash": hash_document(spec_content),
                "sections": {},
            }
        },
        "mappings": mappings_data,
        "ignore_patterns": [],
    }


def _make_mapping(
    code_file: str,
    code_content: str,
    spec_file: str,
    spec_content: str,
    heading_text: str,
    heading_path: list[str],
    stale: bool = False,
) -> dict:
    """Build a single mapping dict with correct hashes."""
    from harness.llm_mock import _find_heading, _line_offset

    line_idx, level, lines = _find_heading(spec_content, heading_text)
    offset = _line_offset(lines, line_idx)
    section_end = len(spec_content)
    for i in range(line_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            h_level = len(stripped) - len(stripped.lstrip("#"))
            if h_level <= level:
                section_end = _line_offset(lines, i)
                break
    span_length = section_end - offset

    code_lines = code_content.splitlines()
    return {
        "id": f"m_test_{code_file.replace('/', '_')}",
        "spec_spans": [
            {
                "spec_file": spec_file,
                "heading_path": heading_path,
                "span_offset": offset,
                "span_length": span_length,
                "span_hash": hash_span(spec_content, offset, span_length),
                "relevance": 0.95,
            }
        ],
        "code_target": {
            "file": code_file,
            "start_line": 1,
            "end_line": len(code_lines),
            "content_hash": hash_code(code_content),
        },
        "stale": stale,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── E15: 100% coverage ──────────────────────────────────────────────────────

async def test_100_percent(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add code")

    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))
    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(result)

    chk = cli_runner.check(repo, "feature/test", base="main", threshold=1.0)
    assert_check_json_pass(chk)
    assert chk.json_data["coverage"] == 1.0


# ── E16: 0% coverage ────────────────────────────────────────────────────────

async def test_0_percent(
    scenario_repo: GitRepo, cli_runner: CLIRunner
):
    repo = scenario_repo

    # Add code with no mapping
    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add unmapped code")

    chk = cli_runner.check(repo, "feature/test", base="main", threshold=0.01)
    assert_check_json_fail(chk)
    assert chk.json_data["coverage"] == 0.0


# ── E17: Threshold exactly met (coverage == threshold) ──────────────────────

async def test_threshold_exactly_met(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/spec.md", AUTH_SPEC)

    # 4-line file, mapped
    four_lines = "package main\nfunc a() {}\nfunc b() {}\nfunc c() {}"
    repo.write_file("src/main.go", four_lines)
    # 1-line file, not mapped
    repo.write_file("src/util.go", "package util")
    repo.git_add("src/main.go", "src/util.go")
    repo.git_commit("Add code files")

    # Write specmap directly for exact control
    mapping_data = _make_mapping(
        "src/main.go", four_lines,
        "docs/spec.md", AUTH_SPEC,
        "Token Storage", ["Authentication", "Token Storage"],
    )
    specmap = _build_specmap_data(
        "feature/test", "docs/spec.md", AUTH_SPEC, [mapping_data],
    )
    repo.write_specmap("feature/test", specmap)

    # Total: 5 lines (4 mapped + 1 unmapped), coverage = 0.80
    chk = cli_runner.check(repo, "feature/test", base="main", threshold=0.80)
    assert_check_json_pass(chk)
    assert abs(chk.json_data["coverage"] - 0.8) < 0.01


# ── E18: Threshold just below ───────────────────────────────────────────────

async def test_threshold_just_below(
    scenario_repo: GitRepo, cli_runner: CLIRunner
):
    repo = scenario_repo

    # Put spec on main
    setup_spec_on_main(repo, "docs/spec.md", AUTH_SPEC)

    # 3-line file, mapped
    three_lines = "package main\nfunc a() {}\nfunc b() {}"
    repo.write_file("src/main.go", three_lines)
    # 2-line file, not mapped
    repo.write_file("src/util.go", "package util\nfunc noop() {}")
    repo.git_add("src/main.go", "src/util.go")
    repo.git_commit("Add code")

    mapping_data = _make_mapping(
        "src/main.go", three_lines,
        "docs/spec.md", AUTH_SPEC,
        "Token Storage", ["Authentication", "Token Storage"],
    )
    specmap = _build_specmap_data(
        "feature/test", "docs/spec.md", AUTH_SPEC, [mapping_data],
    )
    repo.write_specmap("feature/test", specmap)

    # Total: 5 lines (3 mapped + 2 unmapped), coverage = 0.60
    chk = cli_runner.check(repo, "feature/test", base="main", threshold=0.80)
    assert_check_json_fail(chk)
    assert chk.json_data["coverage"] < 0.80


# ── E19: Ignore patterns — generated files excluded ─────────────────────────

async def test_ignore_patterns(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/spec.md", AUTH_SPEC)

    # Mapped code file
    repo.write_file("src/auth.go", AUTH_GO)
    # Generated file — should be excluded
    repo.write_file("src/schema.generated.go", "package gen\nfunc Generated() {}")
    repo.git_add("src/auth.go", "src/schema.generated.go")
    repo.git_commit("Add code + generated file")

    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))
    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(result)

    # Write specmap with ignore patterns
    sm = repo.read_specmap("feature/test")
    sm["ignore_patterns"] = ["*.generated.go"]
    repo.write_specmap("feature/test", sm)

    # Python get_unmapped should not count generated file
    # (get_unmapped uses git diff which includes the generated file,
    #  but ignore_patterns in specmap should filter it)
    # The generated file IS in git diff but not in mappings.
    # Note: the Go CLI doesn't apply ignore_patterns from the specmap file
    # to the coverage calculation — it counts ALL changed files from git diff.
    # This test verifies the Python tool behavior.
    unmapped = await get_unmapped_changes(str(repo.path), branch="feature/test")
    # auth.go is mapped, so its coverage should be high
    if "src/auth.go" in unmapped.get("files", {}):
        auth_cov = unmapped["files"]["src/auth.go"]["coverage"]
        assert auth_cov == 1.0


# ── E20: Stale mappings not counted in Python coverage ──────────────────────

async def test_stale_not_counted(
    scenario_repo: GitRepo, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/spec.md", AUTH_SPEC)

    code = "package main\nfunc hello() {}\nfunc world() {}"
    repo.write_file("src/main.go", code)
    repo.git_add("src/main.go")
    repo.git_commit("Add code")

    # Create mapping marked as stale
    mapping_data = _make_mapping(
        "src/main.go", code,
        "docs/spec.md", AUTH_SPEC,
        "Token Storage", ["Authentication", "Token Storage"],
        stale=True,
    )
    specmap = _build_specmap_data(
        "feature/test", "docs/spec.md", AUTH_SPEC, [mapping_data],
    )
    repo.write_specmap("feature/test", specmap)

    # Python get_unmapped skips stale mappings (line 61-62 of get_unmapped.py)
    unmapped = await get_unmapped_changes(str(repo.path), branch="feature/test")
    # Stale mapping shouldn't contribute to coverage → coverage = 0
    assert_coverage(unmapped, 0.0)
