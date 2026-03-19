"""A. Greenfield scenarios — new repo: spec -> code -> map -> validate -> check."""

from __future__ import annotations

import pytest

from harness.spec_content import AUTH_SPEC, API_SPEC
from harness.code_content import AUTH_GO, AUTH_GO_PARTIAL, API_GO
from harness.llm_mock import build_mapping_for_spec, LLMMockRegistry
from harness.assertions import (
    assert_map_ok,
    assert_pass,
    assert_all_valid,
    assert_check_json_pass,
    assert_check_json_fail,
)
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.map_code_to_spec import map_code_to_spec
from specmap.llm.schemas import MappingResponse

from conftest import setup_spec_on_main


# ── A1: Full coverage roundtrip ──────────────────────────────────────────────

async def test_full_coverage_roundtrip(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/auth-spec.md", AUTH_SPEC)

    # Add code on feature branch
    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth implementation")

    # Register LLM mock → map to Token Storage section
    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))

    # Map
    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(result)

    # Verify specmap file was written
    assert repo.specmap_exists("feature/test")

    # CLI validate — all hashes should match
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)

    # CLI check — 100% coverage (all changed lines mapped)
    chk = cli_runner.check(repo, "feature/test", base="main", threshold=0.0)
    assert_check_json_pass(chk)
    assert chk.json_data["coverage"] == 1.0


# ── A2: Partial coverage with threshold ──────────────────────────────────────

async def test_partial_coverage_threshold(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/auth-spec.md", AUTH_SPEC)

    # Two code files on feature branch
    repo.write_file("src/auth.go", AUTH_GO)
    repo.write_file("src/api.go", API_GO)
    repo.git_add("src/auth.go", "src/api.go")
    repo.git_commit("Add auth and API code")

    # Mock maps only auth.go → partial coverage
    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))

    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(result)

    # Coverage < 1.0 (api.go lines are unmapped)
    chk = cli_runner.check(repo, "feature/test", base="main", threshold=0.0)
    assert_check_json_pass(chk)
    assert chk.json_data["coverage"] < 1.0

    # Low threshold passes
    chk_low = cli_runner.check(repo, "feature/test", base="main", threshold=0.3)
    assert_check_json_pass(chk_low)

    # Threshold 1.0 fails
    chk_high = cli_runner.check(repo, "feature/test", base="main", threshold=1.0)
    assert_check_json_fail(chk_high)


# ── A3: Multi spec, multi code ───────────────────────────────────────────────

async def test_multi_spec_multi_code(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo

    # Two spec files on main
    setup_spec_on_main(repo,"docs/auth-spec.md", AUTH_SPEC)
    setup_spec_on_main(repo, "docs/api-spec.md", API_SPEC)

    # Three code files on feature
    repo.write_file("src/auth.go", AUTH_GO)
    repo.write_file("src/api.go", API_GO)
    repo.write_file("src/util.py", "def helper(): pass")
    repo.git_add("src/auth.go", "src/api.go", "src/util.py")
    repo.git_commit("Add implementation files")

    # Map auth.go → auth-spec, api.go → api-spec
    auth_mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        ["Authentication", "Token Storage"],
    )
    api_mapping = build_mapping_for_spec(
        API_SPEC, "Endpoints", "docs/api-spec.md",
        ["API Design", "Endpoints"],
    )

    # First map call: auth.go
    llm_mock.on_mapping(MappingResponse(mappings=[auth_mapping]))
    r1 = await map_code_to_spec(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_map_ok(r1)

    # Clear and register new mock for api.go
    llm_mock._responses.clear()
    llm_mock.on_mapping(MappingResponse(mappings=[api_mapping]))
    r2 = await map_code_to_spec(
        str(repo.path), code_changes=["src/api.go"], branch="feature/test",
    )
    assert_map_ok(r2)

    # Total mappings should be >= 2
    specmap = repo.read_specmap("feature/test")
    assert len(specmap["mappings"]) >= 2

    # CLI validate passes for both
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)
