"""GitRepo helper: temp repos, file ops, git ops."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


class GitRepo:
    """Wrapper around a git repository in a temp directory."""

    def __init__(self, path: Path):
        self.path = path

    def write_file(self, rel_path: str, content: str) -> Path:
        full = self.path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return full

    def delete_file(self, rel_path: str) -> None:
        (self.path / rel_path).unlink()

    def read_file(self, rel_path: str) -> str:
        return (self.path / rel_path).read_text(encoding="utf-8")

    def file_exists(self, rel_path: str) -> bool:
        return (self.path / rel_path).exists()

    # --- git operations ---

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.path),
            capture_output=True,
            text=True,
            check=check,
        )

    def git_add(self, *paths: str) -> None:
        self._git("add", *paths)

    def git_commit(self, message: str) -> None:
        self._git("commit", "-m", message)

    def git_branch(self, name: str) -> None:
        self._git("checkout", "-b", name)

    def git_checkout(self, name: str) -> None:
        self._git("checkout", name)

    def git_merge(self, branch: str) -> None:
        self._git("merge", branch, "--no-edit")

    def git_current_branch(self) -> str:
        r = self._git("rev-parse", "--abbrev-ref", "HEAD")
        return r.stdout.strip()

    # --- specmap file helpers ---

    def read_specmap(self, branch: str) -> dict:
        sanitized = branch.replace("/", "--")
        path = self.path / ".specmap" / f"{sanitized}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def specmap_exists(self, branch: str) -> bool:
        sanitized = branch.replace("/", "--")
        return (self.path / ".specmap" / f"{sanitized}.json").exists()

    def write_specmap(self, branch: str, data: dict) -> None:
        """Write a .specmap JSON file directly (for tests needing exact control)."""
        sanitized = branch.replace("/", "--")
        specmap_dir = self.path / ".specmap"
        specmap_dir.mkdir(exist_ok=True)
        path = specmap_dir / f"{sanitized}.json"
        path.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )


def create_scenario_repo(tmp_path: Path) -> GitRepo:
    """Create a temp git repo with main branch and feature/test branch.

    Layout after creation:
      - main branch with a single .gitkeep commit
      - feature/test branch checked out
      - .specmap/ directory exists
    """
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
        )

    git("init")
    git("config", "user.email", "test@test.com")
    git("config", "user.name", "Test")

    # Initial commit on default branch
    (repo_path / ".gitkeep").touch()
    (repo_path / ".specmap").mkdir()
    git("add", ".gitkeep")
    git("commit", "-m", "Initial commit")

    # Ensure branch is called 'main'
    git("branch", "-M", "main")

    # Create and checkout feature branch
    git("checkout", "-b", "feature/test")

    return GitRepo(repo_path)
