"""D. Branch scenarios — feature branches, cumulative diffs."""

from __future__ import annotations

import pytest

from harness.spec_content import AUTH_SPEC, API_SPEC
from harness.code_content import AUTH_GO, API_GO
from harness.llm_mock import build_annotation_for_spec, LLMMockRegistry
from harness.assertions import assert_annotate_ok
from harness.repo import GitRepo

from specmap.tools.annotate import annotate
from specmap.llm.schemas import AnnotationResponse

from conftest import setup_spec_on_main


# ── D12: Feature branch annotation vs main ───────────────────────────────────

async def test_feature_branch_annotation_vs_main(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth on feature")

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

    # Annotations were created for the feature branch
    specmap = repo.read_specmap("feature/test")
    assert len(specmap["annotations"]) >= 1
    assert specmap["annotations"][0]["file"] == "src/auth.go"


# ── D13: Multiple commits, cumulative annotations ────────────────────────────

async def test_multiple_commits_cumulative(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    # Also add API spec on main
    setup_spec_on_main(repo, "docs/api-spec.md", API_SPEC)

    # Commit 1: auth.go
    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Commit 1: auth")

    auth_ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[auth_ann]))
    r1 = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(r1)

    # Commit 2: api.go
    repo.write_file("src/api.go", API_GO)
    repo.git_add("src/api.go")
    repo.git_commit("Commit 2: api")

    api_ann = build_annotation_for_spec(
        API_SPEC, "Endpoints", "docs/api-spec.md",
        "API Design > Endpoints",
        code_file="src/api.go",
        code_start=1,
        code_end=len(API_GO.splitlines()),
    )
    llm_mock._responses.clear()
    llm_mock.on_annotation(AnnotationResponse(annotations=[api_ann]))
    r2 = await annotate(
        str(repo.path), code_changes=["src/api.go"], branch="feature/test",
    )
    assert_annotate_ok(r2)

    # Both annotations contribute cumulatively
    specmap = repo.read_specmap("feature/test")
    annotated_files = {a["file"] for a in specmap["annotations"]}
    assert "src/auth.go" in annotated_files
    assert "src/api.go" in annotated_files


# ── D14: No changes — empty annotations ──────────────────────────────────────

async def test_no_changes_empty(scenario_repo: GitRepo):
    repo = scenario_repo
    # Feature branch identical to main — no changes, no annotations
    specmap_path = repo.path / ".specmap" / "feature%2Ftest.json"
    assert not specmap_path.exists()
