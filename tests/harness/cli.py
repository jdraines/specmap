"""Run Python CLI via subprocess."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass

from harness.repo import GitRepo


@dataclass
class CLIResult:
    """Result of a CLI invocation."""
    returncode: int
    stdout: str
    stderr: str
    json_data: dict | None = None


class CLIRunner:
    """Runs the specmap Python CLI."""

    def _run(self, repo: GitRepo, global_args: list[str], cmd_args: list[str]) -> CLIResult:
        cmd = [
            sys.executable, "-m", "specmap.cli",
            "--repo-root", str(repo.path),
            "--no-color",
            *global_args,
            *cmd_args,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(repo.path)
        )
        json_data = None
        args = global_args + cmd_args
        if "--json" in args:
            try:
                json_data = json.loads(result.stdout)
            except (json.JSONDecodeError, ValueError):
                pass
        return CLIResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            json_data=json_data,
        )

    def validate(self, repo: GitRepo, branch: str) -> CLIResult:
        return self._run(repo, ["--branch", branch], ["validate"])

    def status(self, repo: GitRepo, branch: str) -> CLIResult:
        return self._run(repo, ["--branch", branch], ["status"])

    def check(
        self,
        repo: GitRepo,
        branch: str,
        base: str = "main",
        threshold: float = 0.0,
        json_output: bool = True,
    ) -> CLIResult:
        cmd_args = [
            "check",
            "--base", base,
            "--threshold", str(threshold),
        ]
        if json_output:
            cmd_args.append("--json")
        return self._run(repo, ["--branch", branch], cmd_args)
