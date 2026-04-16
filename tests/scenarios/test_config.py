"""F. Configuration — custom patterns, env vars, ignore rules."""

from __future__ import annotations

import json
import os

import pytest

from harness.spec_content import AUTH_SPEC
from harness.code_content import AUTH_GO
from harness.llm_mock import build_annotation_for_spec, LLMMockRegistry
from harness.assertions import assert_annotate_ok
from harness.repo import GitRepo

from specmap.tools.annotate import annotate
from specmap.llm.schemas import AnnotationResponse
from specmap.config import CoreConfig


# ── F21: Custom spec patterns ────────────────────────────────────────────────

async def test_custom_spec_patterns(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo

    # Write config with custom spec_patterns
    config = {"spec_patterns": ["specs/*.txt"]}
    repo.write_file(".specmap/config.json", json.dumps(config))

    # Create a .txt spec in specs/ (matches pattern)
    txt_spec = "# Auth Spec\n\n## Token Storage\n\nTokens stored here.\n"
    repo.write_file("specs/auth.txt", txt_spec)

    # Create a .md spec in docs/ (should NOT match)
    repo.write_file("docs/auth-spec.md", AUTH_SPEC)

    repo.write_file("src/auth.go", AUTH_GO)
    repo.git_add("specs/auth.txt", "docs/auth-spec.md", "src/auth.go", ".specmap/config.json")
    repo.git_commit("Add specs and code")

    # Mock annotates with ref to the .txt spec
    ann = build_annotation_for_spec(
        txt_spec, "Token Storage", "specs/auth.txt",
        "Auth Spec > Token Storage",
        code_file="src/auth.go",
        code_start=1,
        code_end=len(AUTH_GO.splitlines()),
    )
    llm_mock.on_annotation(AnnotationResponse(annotations=[ann]))

    result = await annotate(
        str(repo.path), code_changes=["src/auth.go"], branch="feature/test",
    )
    assert_annotate_ok(result)

    # Verify specs/auth.txt was found as a spec (it's referenced in annotations)
    sm = repo.read_specmap("feature/test")
    ref_spec_files = set()
    for a in sm.get("annotations", []):
        for ref in a.get("refs", []):
            ref_spec_files.add(ref["spec_file"])
    assert "specs/auth.txt" in ref_spec_files


# ── F22: Custom ignore patterns ─────────────────────────────────────────────

async def test_custom_ignore_patterns(
    scenario_repo: GitRepo, llm_mock: LLMMockRegistry
):
    repo = scenario_repo

    # Write config that ignores test files
    config = {"ignore_patterns": ["*_test.go", "*.generated.go"]}
    repo.write_file(".specmap/config.json", json.dumps(config))

    repo.git_checkout("main")
    repo.write_file("docs/spec.md", AUTH_SPEC)
    repo.git_add("docs/spec.md", ".specmap/config.json")
    repo.git_commit("Add spec and config")
    repo.git_checkout("feature/test")
    repo.git_merge("main")

    # Create test file and regular file
    repo.write_file("src/auth.go", AUTH_GO)
    repo.write_file("src/auth_test.go", "package auth\nfunc TestAuth() {}")
    repo.git_add("src/auth.go", "src/auth_test.go")
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
        str(repo.path), code_changes=["src/auth.go", "src/auth_test.go"],
        branch="feature/test",
    )
    # annotate filters ignored files — auth_test.go should be skipped
    assert result["status"] == "ok"

    # Verify test file is not in annotations
    sm = repo.read_specmap("feature/test")
    annotated_files = {a["file"] for a in sm["annotations"]}
    assert "src/auth_test.go" not in annotated_files


# ── F23: Env vars override config file ──────────────────────────────────────

def test_env_vars_override_config(scenario_repo: GitRepo, monkeypatch):
    repo = scenario_repo

    # Config file sets one model
    config = {"model": "gpt-3.5-turbo"}
    repo.write_file(".specmap/config.json", json.dumps(config))

    # Env var overrides
    monkeypatch.setenv("SPECMAP_MODEL", "claude-opus-4-6")

    loaded = CoreConfig.load(str(repo.path))
    assert loaded.model == "claude-opus-4-6"
