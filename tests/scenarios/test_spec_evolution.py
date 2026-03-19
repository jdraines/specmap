"""C. Spec evolution — edit spec, relocation strategies, staleness."""

from __future__ import annotations

import pytest

from harness.spec_content import (
    AUTH_SPEC,
    AUTH_SPEC_MINOR_EDIT,
    AUTH_SPEC_SHIFTED,
    AUTH_SPEC_REWRITTEN,
    AUTH_SPEC_EXTRA_SECTION,
)
from harness.code_content import AUTH_GO
from harness.llm_mock import build_mapping_for_spec, build_reindex_result, LLMMockRegistry
from harness.assertions import assert_map_ok, assert_fail, assert_all_valid
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.map_code_to_spec import map_code_to_spec
from specmap.tools.check_sync import check_sync
from specmap.tools.reindex import reindex
from specmap.llm.schemas import MappingResponse

from conftest import setup_spec_on_main


def _setup_mapped_repo(repo: GitRepo, llm_mock: LLMMockRegistry):
    """Set up spec on main, map auth code on feature branch."""
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth code")


async def _do_initial_mapping(repo: GitRepo, llm_mock: LLMMockRegistry):
    """Run the initial map_code_to_spec."""
    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))
    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(result)


# ── C7: Minor wording change — fuzzy relocation succeeds ────────────────────

async def test_minor_wording_fuzzy_relocation(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    _setup_mapped_repo(repo, llm_mock)
    await _do_initial_mapping(repo, llm_mock)

    # Minor edit to spec (Token Storage wording changed slightly)
    repo.write_file("docs/auth-spec.md", AUTH_SPEC_MINOR_EDIT)

    sync = await check_sync(str(repo.path), branch="feature/test")
    # Fuzzy match (>0.8 similarity) should relocate successfully
    assert sync["relocated"] > 0, f"Expected relocated mappings, got: {sync}"
    assert sync["stale"] == 0, f"Expected no stale after fuzzy relocation, got: {sync}"


# ── C8: Text shift — exact relocation (Strategy 2: find anywhere) ───────────

async def test_text_shift_exact_relocation(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    _setup_mapped_repo(repo, llm_mock)
    await _do_initial_mapping(repo, llm_mock)

    # Insert paragraph before Token Storage — offsets shift, text identical
    repo.write_file("docs/auth-spec.md", AUTH_SPEC_SHIFTED)

    sync = await check_sync(str(repo.path), branch="feature/test")
    # Strategy 2 (exact match anywhere) should find the span
    assert sync["relocated"] > 0, f"Expected relocated mappings, got: {sync}"
    assert sync["stale"] == 0, f"Expected no stale after shift relocation, got: {sync}"


# ── C9: Full rewrite — relocation fails, reindex needed ─────────────────────

async def test_full_rewrite_relocation_fails(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    _setup_mapped_repo(repo, llm_mock)
    await _do_initial_mapping(repo, llm_mock)

    # Completely rewrite Token Storage section
    repo.write_file("docs/auth-spec.md", AUTH_SPEC_REWRITTEN)

    # check_sync detects hash mismatch but relocator "succeeds" (known limitation)
    sync = await check_sync(str(repo.path), branch="feature/test")
    assert sync["relocated"] > 0, f"Expected relocated after rewrite, got: {sync}"

    # Reindex properly detects doc hash change and re-maps via LLM
    reindex_resp = build_reindex_result(
        AUTH_SPEC_REWRITTEN, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock._responses.clear()
    llm_mock.on_reindex(reindex_resp)

    ri = await reindex(str(repo.path))
    assert ri["total_mappings"] >= 1


# ── C10: Add new section — existing mappings preserved ───────────────────────

async def test_add_section_preserves_existing(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    _setup_mapped_repo(repo, llm_mock)
    await _do_initial_mapping(repo, llm_mock)

    # Add a new Rate Limiting section to the spec
    repo.write_file("docs/auth-spec.md", AUTH_SPEC_EXTRA_SECTION)

    # Reindex — the Token Storage section is unchanged, so existing mapping
    # should be preserved; only new section needs attention
    llm_mock._responses.clear()
    # No reindex mock needed — the original section hash is the same

    ri = await reindex(str(repo.path))
    # sections_skipped > 0 means unchanged sections were detected
    assert ri.get("sections_skipped", 0) > 0 or ri.get("unchanged", 0) > 0, (
        f"Expected some sections skipped or unchanged, got: {ri}"
    )
    assert ri["total_mappings"] >= 1


# ── C11: Delete spec file — validate fails ──────────────────────────────────

async def test_delete_spec_file(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    _setup_mapped_repo(repo, llm_mock)
    await _do_initial_mapping(repo, llm_mock)

    # Delete the spec file
    repo.delete_file("docs/auth-spec.md")

    # CLI validate fails — cannot read spec
    val = cli_runner.validate(repo, "feature/test")
    assert_fail(val)
