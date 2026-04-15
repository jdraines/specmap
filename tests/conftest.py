"""Session fixtures for functional tests: CLI runner, shared config."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the tests/ directory is importable for harness modules
_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))

# Ensure core/src is importable (specmap package)
_core_src = Path(__file__).resolve().parent.parent / "src"
if str(_core_src) not in sys.path:
    sys.path.insert(0, str(_core_src))

from harness.repo import GitRepo, create_scenario_repo
from harness.llm_mock import LLMMockRegistry
from harness.cli import CLIRunner


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")


# ---------------------------------------------------------------------------
# Function-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scenario_repo(tmp_path) -> GitRepo:
    """Fresh temp git repo: main branch with .gitkeep, feature/test checked out."""
    return create_scenario_repo(tmp_path)


@pytest.fixture
def llm_mock(monkeypatch) -> LLMMockRegistry:
    """Mock litellm.acompletion for the duration of a test."""
    import litellm

    registry = LLMMockRegistry()
    monkeypatch.setattr(litellm, "acompletion", registry.mock_acompletion)
    return registry


@pytest.fixture
def cli_runner() -> CLIRunner:
    """CLIRunner using Python CLI (no binary needed)."""
    return CLIRunner()


# ---------------------------------------------------------------------------
# Shared helpers available to all tests via import
# ---------------------------------------------------------------------------

def setup_spec_on_main(repo: GitRepo, spec_path: str, content: str) -> None:
    """Add spec file to main and merge into feature branch.

    This ensures the spec is available in the feature branch working tree
    but does NOT appear in ``git diff main...HEAD`` (since it's on main).
    """
    repo.git_checkout("main")
    repo.write_file(spec_path, content)
    repo.git_add(spec_path)
    repo.git_commit(f"Add {spec_path}")
    repo.git_checkout("feature/test")
    repo.git_merge("main")
