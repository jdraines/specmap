"""A. Greenfield scenarios — new repo: spec -> code -> annotate -> validate."""

from __future__ import annotations

import pytest

from harness.spec_content import AUTH_SPEC, API_SPEC
from harness.code_content import AUTH_GO, AUTH_GO_PARTIAL, API_GO
from harness.llm_mock import build_annotation_for_spec, LLMMockRegistry
from harness.assertions import (
    assert_annotate_ok,
    assert_pass,
    assert_all_valid,
)
from harness.repo import GitRepo
from harness.cli import CLIRunner

from specmap.tools.annotate import annotate
from specmap.llm.schemas import AnnotationResponse

from conftest import setup_spec_on_main


# ── A1: Full coverage roundtrip ──────────────────────────────────────────────

async def test_full_coverage_roundtrip(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    # Add code on feature branch
    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("src/auth.go")
    repo.git_commit("Add auth implementation")

    # Register LLM mock → annotate with Token Storage ref
    ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[ann]))

    # Annotate
    result = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(result)

    # Verify specmap file was written
    assert repo.specmap_exists("feature/test")

    # CLI validate — all line ranges should be valid
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── A2: Partial coverage with threshold ──────────────────────────────────────

async def test_partial_coverage_threshold(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)

    # Two code files on feature branch
    repo.write_file("src/auth.go", AUTH_GO)
    repo.write_file("src/api.go", API_GO)
    repo.git_add("src/auth.go", "src/api.go")
    repo.git_commit("Add auth and API code")

    # Mock annotates only auth.go → partial coverage
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

    # Annotations exist but only for auth.go — api.go is unannotated
    specmap = repo.read_specmap("feature/test")
    annotated_files = {a["file"] for a in specmap["annotations"]}
    assert "src/auth.go" in annotated_files
    assert "src/api.go" not in annotated_files


# ── A3: Multi spec, multi code ───────────────────────────────────────────────

async def test_multi_spec_multi_code(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry, cli_runner: CLIRunner
):
    repo = scenario_repo

    # Two spec files on main
    setup_spec_on_main(repo, "docs/auth-spec.md", AUTH_SPEC)
    setup_spec_on_main(repo, "docs/api-spec.md", API_SPEC)

    # Three code files on feature
    repo.write_file("src/auth.go", AUTH_GO)
    repo.write_file("src/api.go", API_GO)
    repo.write_file("src/util.py", "def helper(): pass")
    repo.git_add("src/auth.go", "src/api.go", "src/util.py")
    repo.git_commit("Add implementation files")

    # Annotate auth.go → auth-spec
    auth_ann = build_annotation_for_spec(
        AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
        "Authentication > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )

    api_ann = build_annotation_for_spec(
        API_SPEC, "Endpoints", "docs/api-spec.md",
        "API Design > Endpoints",
        code_file="src/api.go",
        code_start=1,
        code_end=len(API_GO.splitlines()),
    )

    # First annotate call: auth.go
    llm_mock.on_annotation(AnnotationResponse(annotations=[auth_ann]))
    r1 = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(r1)

    # Clear and register new mock for api.go
    llm_mock._responses.clear()
    llm_mock.on_annotation(AnnotationResponse(annotations=[api_ann]))
    r2 = await annotate(
        str(repo.path), code_changes=["src/api.go"], branch="feature/test",
    )
    assert_annotate_ok(r2)

    # Total annotations should be >= 2
    specmap = repo.read_specmap("feature/test")
    assert len(specmap["annotations"]) >= 2

    # CLI validate passes for both
    val = cli_runner.validate(repo, "feature/test")
    assert_all_valid(val)


# ── A4: Context parameter reaches LLM prompt ────────────────────────────────

async def test_context_parameter(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    """Verify that the context parameter is passed through to the LLM prompt."""
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

    context_str = "Use bcrypt not argon2 for password hashing. TTL should be configurable."
    result = await annotate(
        str(repo.path),
        code_changes=["src/auth.go"],
        branch="feature/test",
        context=context_str,
    )
    assert_annotate_ok(result)

    # Verify the LLM mock received messages containing the context string
    assert llm_mock.call_count >= 1
    last_messages = llm_mock.last_messages
    assert last_messages is not None
    # The context should appear in the user message
    user_messages = [m["content"] for m in last_messages if m["role"] == "user"]
    assert any(context_str in msg for msg in user_messages), (
        f"Context string not found in LLM messages: {user_messages}"
    )
