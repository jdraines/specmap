"""G. Error cases — empty repos, missing files, unicode, deep headings."""

from __future__ import annotations

import pytest

from harness.spec_content import AUTH_SPEC, DEEP_SPEC, UNICODE_SPEC, EMPTY_SPEC
from harness.code_content import AUTH_GO, UNICODE_CODE
from harness.llm_mock import build_mapping_for_spec, LLMMockRegistry
from harness.assertions import assert_map_ok, assert_all_valid
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.map_code_to_spec import map_code_to_spec
from specmap.tools.get_unmapped import get_unmapped_changes
from specmap.llm.schemas import MappingResponse

from conftest import setup_spec_on_main


# ── G24: Empty repo — no specs, no code ─────────────────────────────────────

async def test_empty_repo(scenario_repo: GitRepo, llm_mock: LLMMockRegistry):
    repo = scenario_repo
    # No specs, no code changes
    result = await map_code_to_spec(str(repo.path), branch="feature/test")
    assert result["status"] == "no_specs"
    assert result["mappings_created"] == 0

    # get_unmapped with nothing should report 100% (nothing to cover)
    unmapped = await get_unmapped_changes(str(repo.path), branch="feature/test")
    assert unmapped["overall_coverage"] == 1.0


# ── G25: Spec with no headings ──────────────────────────────────────────────

async def test_spec_no_headings(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/empty.md", EMPTY_SPEC)

    repo.write_file("src/main.go", AUTH_GO)
    repo.git_add("src/main.go")
    repo.git_commit("Add code")

    # LLM returns empty mappings (no headings to map to)
    llm_mock.on_mapping(MappingResponse(mappings=[]))

    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/main.go"], branch="feature/test",
    )
    # Should not crash; may report no_changes or ok with 0 mappings
    assert result["status"] in ("ok", "no_changes")


# ── G26: Deep heading hierarchy (5 levels) ──────────────────────────────────

async def test_deep_heading_hierarchy(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/deep.md", DEEP_SPEC)

    repo.write_file("src/main.go", AUTH_GO)
    repo.git_add("src/main.go")
    repo.git_commit("Add code")

    # Map to the deepest heading (Level 5)
    mapping = build_mapping_for_spec(
        DEEP_SPEC, "Level 5", "docs/deep.md",
        ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))

    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/main.go"], branch="feature/test",
    )
    assert_map_ok(result)

    # Verify heading_path has 5 entries
    sm = repo.read_specmap("feature/test")
    spans = sm["mappings"][0]["spec_spans"]
    assert len(spans[0]["heading_path"]) == 5

    # CLI validate passes
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── G27: Unicode content — non-ASCII in specs and code ──────────────────────

async def test_unicode_content(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/unicode.md", UNICODE_SPEC)

    repo.write_file("src/main.go", UNICODE_CODE)
    repo.git_add("src/main.go")
    repo.git_commit("Add unicode code")

    mapping = build_mapping_for_spec(
        UNICODE_SPEC, "Token-Speicherung", "docs/unicode.md",
        ["Authentifizierung", "Token-Speicherung"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))

    result = await map_code_to_spec(
        str(repo.path), code_changes=["src/main.go"], branch="feature/test",
    )
    assert_map_ok(result)

    # Hashing works, validate passes
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── G28: Large diff — 10+ files ─────────────────────────────────────────────

@pytest.mark.slow
async def test_large_diff(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    setup_spec_on_main(repo,"docs/spec.md", AUTH_SPEC)

    # Create 12 code files
    for i in range(12):
        content = f"package pkg{i}\nfunc Func{i}() {{}}"
        repo.write_file(f"src/pkg{i}.go", content)
    repo.git_add(".")
    repo.git_commit("Add 12 files")

    # Map each file individually
    mapping = build_mapping_for_spec(
        AUTH_SPEC, "Token Storage", "docs/spec.md",
        ["Authentication", "Token Storage"],
    )
    llm_mock.on_mapping(MappingResponse(mappings=[mapping]))

    total = 0
    for i in range(12):
        result = await map_code_to_spec(
            str(repo.path), code_changes=[f"src/pkg{i}.go"],
            branch="feature/test",
        )
        if result["status"] == "ok":
            total += result["mappings_created"]

    assert total >= 10, f"Expected >= 10 mappings, got {total}"
