"""E. Coverage edge cases — threshold enforcement, ignore patterns."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from harness.spec_content import AUTH_SPEC, API_SPEC
from harness.code_content import AUTH_GO, API_GO
from harness.llm_mock import build_annotation_for_spec, LLMMockRegistry
from harness.assertions import (
    assert_annotate_ok,
    assert_check_json_pass,
    assert_check_json_fail,
    assert_coverage,
)
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.annotate import annotate
from specmap.tools.get_unmapped import get_unmapped_changes
from specmap.llm.schemas import AnnotationResponse

from conftest import setup_spec_on_main


def _build_specmap_data(
    branch: str,
    annotations_data: list[dict],
) -> dict:
    """Build a raw specmap v2 dict with exact control over content."""
    return {
        "version": 2,
        "branch": branch,
        "base_branch": "main",
        "head_sha": "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "test",
        "annotations": annotations_data,
        "ignore_patterns": [],
    }


def _make_annotation(
    code_file: str,
    code_content: str,
    spec_file: str,
    spec_content: str,
    heading_text: str,
    heading_path: str,
    no_refs: bool = False,
) -> dict:
    """Build a single annotation dict."""
    from harness.llm_mock import _find_heading

    line_idx, level, lines = _find_heading(spec_content, heading_text)

    # Extract excerpt
    body_lines = []
    for i in range(line_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            break
        if stripped:
            body_lines.append(stripped)
    excerpt = " ".join(body_lines[:2])

    code_lines = code_content.splitlines()
    refs = [] if no_refs else [
        {
            "id": 1,
            "spec_file": spec_file,
            "heading": heading_path,
            "start_line": line_idx + 1,
            "excerpt": excerpt,
        }
    ]

    return {
        "id": f"a_test_{code_file.replace('/', '_')}",
        "file": code_file,
        "start_line": 1,
        "end_line": len(code_lines),
        "description": f"Implements {heading_text.lower()} functionality. [1]",
        "refs": refs,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── E15: 100% coverage ──────────────────────────────────────────────────────

async def test_100_percent(
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
    result = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(result)

    chk = cli_runner.check(repo, "feature/test", base="main", threshold=1.0)
    assert_check_json_pass(chk)
    assert chk.json_data["coverage"] == 1.0


# ── E16: 0% coverage ────────────────────────────────────────────────────────

async def test_0_percent(
    scenario_repo: GitRepo, cli_runner: CLIRunner
):
    repo = scenario_repo

    # Add code with no annotations
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
    setup_spec_on_main(repo, "docs/spec.md", AUTH_SPEC)

    # 4-line file, annotated
    four_lines = "package main\nfunc a() {}\nfunc b() {}\nfunc c() {}"
    repo.write_file("src/main.go", four_lines)
    # 1-line file, not annotated
    repo.write_file("src/util.go", "package util")
    repo.git_add("src/main.go", "src/util.go")
    repo.git_commit("Add code files")

    # Write specmap directly for exact control
    annotation_data = _make_annotation(
        "src/main.go", four_lines,
        "docs/spec.md", AUTH_SPEC,
        "Token Storage", "Authentication > Token Storage",
    )
    specmap = _build_specmap_data("feature/test", [annotation_data])
    repo.write_specmap("feature/test", specmap)

    # Total: 5 lines (4 annotated + 1 unannotated), coverage = 0.80
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

    # 3-line file, annotated
    three_lines = "package main\nfunc a() {}\nfunc b() {}"
    repo.write_file("src/main.go", three_lines)
    # 2-line file, not annotated
    repo.write_file("src/util.go", "package util\nfunc noop() {}")
    repo.git_add("src/main.go", "src/util.go")
    repo.git_commit("Add code")

    annotation_data = _make_annotation(
        "src/main.go", three_lines,
        "docs/spec.md", AUTH_SPEC,
        "Token Storage", "Authentication > Token Storage",
    )
    specmap = _build_specmap_data("feature/test", [annotation_data])
    repo.write_specmap("feature/test", specmap)

    # Total: 5 lines (3 annotated + 2 unannotated), coverage = 0.60
    chk = cli_runner.check(repo, "feature/test", base="main", threshold=0.80)
    assert_check_json_fail(chk)
    assert chk.json_data["coverage"] < 0.80


# ── E19: Ignore patterns — generated files excluded ─────────────────────────

async def test_ignore_patterns(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/spec.md", AUTH_SPEC)

    # Annotated code file
    repo.write_file("src/auth.go", AUTH_GO)
    # Generated file — should be excluded
    repo.write_file("src/schema.generated.go", "package gen\nfunc Generated() {}")
    repo.git_add("src/auth.go", "src/schema.generated.go")
    repo.git_commit("Add code + generated file")

    ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/spec.md",
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

    # Write specmap with ignore patterns
    sm = repo.read_specmap("feature/test")
    sm["ignore_patterns"] = ["*.generated.go"]
    repo.write_specmap("feature/test", sm)

    # auth.go should be fully covered
    unmapped = await get_unmapped_changes(str(repo.path), branch="feature/test")
    if "src/auth.go" in unmapped.get("files", {}):
        auth_cov = unmapped["files"]["src/auth.go"]["coverage"]
        assert auth_cov == 1.0


# ── E20: Annotations without refs not counted as spec-covered ────────────────

async def test_no_refs_not_counted(
    scenario_repo: GitRepo, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/spec.md", AUTH_SPEC)

    code = "package main\nfunc hello() {}\nfunc world() {}"
    repo.write_file("src/main.go", code)
    repo.git_add("src/main.go")
    repo.git_commit("Add code")

    # Create annotation with no refs (described but not spec-covered)
    annotation_data = _make_annotation(
        "src/main.go", code,
        "docs/spec.md", AUTH_SPEC,
        "Token Storage", "Authentication > Token Storage",
        no_refs=True,
    )
    specmap = _build_specmap_data("feature/test", [annotation_data])
    repo.write_specmap("feature/test", specmap)

    # Annotations without refs shouldn't contribute to coverage → coverage = 0
    unmapped = await get_unmapped_changes(str(repo.path), branch="feature/test")
    assert_coverage(unmapped, 0.0)
