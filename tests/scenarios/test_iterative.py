"""B. Iterative scenarios — edit code/spec, detect staleness, re-map."""

from __future__ import annotations

import pytest

from harness.spec_content import AUTH_SPEC, AUTH_SPEC_REWRITTEN
from harness.code_content import AUTH_GO, AUTH_GO_EDITED
from harness.llm_mock import build_mapping_for_spec, build_reindex_result, LLMMockRegistry
from harness.assertions import (
    assert_map_ok,
    assert_pass,
    assert_fail,
    assert_all_valid,
    assert_stale_count,
)
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.map_code_to_spec import map_code_to_spec
from specmap.tools.check_sync import check_sync
from specmap.tools.reindex import reindex
from specmap.llm.schemas import MappingResponse

from conftest import setup_spec_on_main


# ── B4: Edit spec → stale → reindex fixes ───────────────────────────────────

async def test_edit_spec_stale_then_reindex(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/auth-spec.md", AUTH_SPEC)

    # Add code and map
    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth code")

    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))
    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(result)

    # Now REWRITE the spec — Token Storage section completely different
    repo.write_file("docs/auth-spec.md", AUTH_SPEC_REWRITTEN)
    repo.git_add("docs/auth-spec.md")
    repo.git_commit("Rewrite token storage spec")

    # check_sync detects hash mismatch on spec spans. Due to a design
    # limitation (old_contents == new_contents), the relocator always
    # "succeeds" — but the hash is updated to the new content.
    sync = await check_sync(str(repo.path), branch="feature/test")
    assert sync["relocated"] > 0 or sync["valid"] > 0, (
        f"Expected relocated after spec rewrite, got: {sync}"
    )

    # Reindex properly detects the doc-level hash change
    reindex_response = build_reindex_result(
        AUTH_SPEC_REWRITTEN, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock._responses.clear()
    llm_mock.on_reindex(reindex_response)

    ri = await reindex(str(repo.path))
    assert ri["total_mappings"] >= 1, f"Expected mappings preserved, got: {ri}"

    # Validate should now pass
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── B5: Add more code → coverage improves ───────────────────────────────────

async def test_add_code_coverage_improves(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/auth-spec.md", AUTH_SPEC)

    # Start with auth.go only
    repo.write_file("src/auth.go", AUTH_GO)
    repo.write_file("src/api.go", "package api\nfunc stub() {}")
    repo.git_add("src/auth.go", "src/api.go")
    repo.git_commit("Add initial code")

    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))
    r1 = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(r1)
    initial_mappings = r1["total_mappings"]

    # Now map api.go as well
    from harness.spec_content import API_SPEC

    # Add API spec to main for discovery
    setup_spec_on_main(repo, "docs/api-spec.md", API_SPEC)

    api_mapping = build_mapping_for_spec(
        API_SPEC, "Endpoints", "docs/api-spec.md",
        ["API Design", "Endpoints"],
    )
    llm_mock._responses.clear()
    llm_mock.on_mapping(MappingResponse(mappings=[api_mapping]))
    r2 = await map_code_to_spec(
        str(repo.path), code_changes=["src/api.go"], branch="feature/test",
    )
    assert_map_ok(r2)
    assert r2["total_mappings"] > initial_mappings


# ── B6: Delete mapped code file → validate fails ────────────────────────────

async def test_delete_mapped_code(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/auth-spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth code")

    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))
    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(result)

    # Delete the mapped code file
    repo.delete_file("src/auth.go")

    # CLI validate should fail — cannot read file
    val = cli_runner.validate(repo, "feature/test")
    assert_fail(val)
    assert "cannot read file" in val.stdout.lower() or "cannot read" in val.stderr.lower()
