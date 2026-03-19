"""Tests for SpecmapFileManager load/save."""

from __future__ import annotations

import json
from pathlib import Path

from specmap_mcp.state.models import SpecmapFile
from specmap_mcp.state.specmap_file import SpecmapFileManager


def test_ensure_dir(tmp_repo: Path):
    """ensure_dir creates .specmap/ directory."""
    mgr = SpecmapFileManager(str(tmp_repo))
    mgr.ensure_dir()
    assert (tmp_repo / ".specmap").is_dir()


def test_get_branch(tmp_repo: Path):
    """get_branch returns the current git branch."""
    mgr = SpecmapFileManager(str(tmp_repo))
    branch = mgr.get_branch()
    # After git init, branch is usually "main" or "master"
    assert branch in ("main", "master")


def test_get_base_branch(tmp_repo: Path):
    """get_base_branch detects main or master."""
    mgr = SpecmapFileManager(str(tmp_repo))
    base = mgr.get_base_branch()
    assert base in ("main", "master")


def test_load_nonexistent(tmp_repo: Path):
    """Loading a nonexistent branch file returns empty SpecmapFile."""
    mgr = SpecmapFileManager(str(tmp_repo))
    data = mgr.load("nonexistent-branch")
    assert data.branch == "nonexistent-branch"
    assert data.mappings == []
    assert data.spec_documents == {}


def test_save_and_load(tmp_repo: Path):
    """Save then load should round-trip the data."""
    mgr = SpecmapFileManager(str(tmp_repo))

    original = SpecmapFile(branch="test-branch", base_branch="main")
    path = mgr.save(original)

    assert path.exists()
    assert path.name == "test-branch.json"

    loaded = mgr.load("test-branch")
    assert loaded.branch == "test-branch"
    assert loaded.base_branch == "main"
    assert loaded.version == 1


def test_save_branch_sanitization(tmp_repo: Path):
    """Branch names with / should be converted to -- in filenames."""
    mgr = SpecmapFileManager(str(tmp_repo))

    data = SpecmapFile(branch="feature/add-auth", base_branch="main")
    path = mgr.save(data)

    assert path.name == "feature--add-auth.json"
    assert path.exists()


def test_load_sanitized_branch(tmp_repo: Path):
    """Loading with a branch name containing / should find the sanitized file."""
    mgr = SpecmapFileManager(str(tmp_repo))

    data = SpecmapFile(branch="feature/add-auth", base_branch="main")
    mgr.save(data)

    loaded = mgr.load("feature/add-auth")
    assert loaded.branch == "feature/add-auth"


def test_save_creates_pretty_json(tmp_repo: Path):
    """Saved file should be pretty-printed JSON."""
    mgr = SpecmapFileManager(str(tmp_repo))

    data = SpecmapFile(branch="pretty-test", base_branch="main")
    path = mgr.save(data)

    content = path.read_text()
    # Pretty JSON has newlines and indentation
    assert "\n" in content
    parsed = json.loads(content)
    assert parsed["branch"] == "pretty-test"


def test_save_with_sample_data(tmp_repo: Path, sample_specmap: SpecmapFile):
    """Save and load a SpecmapFile with mappings and spec documents."""
    mgr = SpecmapFileManager(str(tmp_repo))

    path = mgr.save(sample_specmap)
    assert path.exists()

    loaded = mgr.load(sample_specmap.branch)
    assert len(loaded.mappings) == 1
    assert len(loaded.spec_documents) == 1
    assert loaded.mappings[0].id == "m_abcdef123456"
    assert loaded.mappings[0].code_target.file == "api/internal/auth/session.go"
