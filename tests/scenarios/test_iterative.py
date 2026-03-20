"""B. Iterative scenarios — edit code, re-annotate, coverage changes."""

from __future__ import annotations

import pytest

from harness.spec_content import AUTH_SPEC
from harness.code_content import AUTH_GO, AUTH_GO_EDITED, API_GO
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
from specmap.llm.schemas import AnnotationResponse

from conftest import setup_spec_on_main


# ── B4: Edit code → re-annotate ─────────────────────────────────────────────

async def test_edit_code_reannotate(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    # Add code and annotate
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

    # Edit the code
    repo.write_file("src/auth.go", AUTH_GO_EDITED)
    repo.git_add("src/auth.go")
    repo.git_commit("Edit auth code - 48h TTL")

    # Re-annotate with updated description
    llm_mock._responses.clear()
    edited_ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO_EDITED.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[edited_ann]))
    result2 = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert result2["status"] == "ok"
    assert result2["total_annotations"] >= 1

    # Validate should pass
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── B5: Add more code → coverage improves ───────────────────────────────────

async def test_add_code_coverage_improves(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    # Start with auth.go only
    repo.write_file("src/auth.go", AUTH_GO)
    repo.write_file("src/api.go", "package api\nfunc stub() {}")
    repo.git_add("src/auth.go", "src/api.go")
    repo.git_commit("Add initial code")

    ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[ann]))
    r1 = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(r1)
    initial_annotations = r1["total_annotations"]

    # Now annotate api.go as well
    from harness.spec_content import API_SPEC

    # Add API spec to main for discovery
    setup_spec_on_main(repo, "docs/api-spec.md", API_SPEC)

    api_ann = build_annotation_for_spec(
        API_SPEC, "Endpoints", "docs/api-spec.md",
        "API Design > Endpoints",
        code_file="src/api.go",
        code_start=1,
        code_end=2,
    )
    llm_mock._responses.clear()
    llm_mock.on_annotation(AnnotationResponse(annotations=[api_ann]))
    r2 = await annotate(
        str(repo.path), code_changes=["src/api.go"], branch="feature/test",
    )
    assert_annotate_ok(r2)
    assert r2["total_annotations"] > initial_annotations


# ── B6: Delete annotated code file → validate fails ─────────────────────────

async def test_delete_annotated_code(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
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

    # Delete the annotated code file
    repo.delete_file("src/auth.go")

    # CLI validate should fail — cannot read file
    val = cli_runner.validate(repo, "feature/test")
    assert_fail(val)
    assert "cannot read file" in val.stdout.lower() or "cannot read" in val.stderr.lower()
