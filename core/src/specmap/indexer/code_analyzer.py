"""Parse unified diffs and analyze code changes."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import unidiff


@dataclass
class CodeChange:
    """A changed region of code."""

    file_path: str
    start_line: int
    end_line: int
    change_type: str  # "added", "modified", "deleted"
    content: str  # the changed lines


class CodeAnalyzer:
    """Analyzes code changes from git diffs."""

    def parse_diff(self, diff_text: str) -> list[CodeChange]:
        """Parse a unified diff string into structured CodeChange objects."""
        if not diff_text.strip():
            return []

        try:
            patchset = unidiff.PatchSet.from_string(diff_text)
        except Exception as e:
            print(f"[specmap] Warning: failed to parse diff: {e}", file=sys.stderr)
            return []

        changes: list[CodeChange] = []

        for patched_file in patchset:
            file_path = patched_file.path
            if not file_path:
                continue

            # Determine change type at file level
            if patched_file.is_added_file:
                file_change_type = "added"
            elif patched_file.is_removed_file:
                file_change_type = "deleted"
            else:
                file_change_type = "modified"

            # Extract changed hunks
            for hunk in patched_file:
                added_lines = []
                min_line = None
                max_line = None

                for line in hunk:
                    if line.is_added:
                        added_lines.append(line.value)
                        if line.target_line_no is not None:
                            if min_line is None or line.target_line_no < min_line:
                                min_line = line.target_line_no
                            if max_line is None or line.target_line_no > max_line:
                                max_line = line.target_line_no
                    elif line.is_removed and file_change_type == "deleted":
                        added_lines.append(line.value)
                        if line.source_line_no is not None:
                            if min_line is None or line.source_line_no < min_line:
                                min_line = line.source_line_no
                            if max_line is None or line.source_line_no > max_line:
                                max_line = line.source_line_no

                # For modified files, also include context of removed lines
                if file_change_type == "modified" and not added_lines:
                    for line in hunk:
                        if line.is_removed:
                            added_lines.append(line.value)
                            if line.source_line_no is not None:
                                if min_line is None or line.source_line_no < min_line:
                                    min_line = line.source_line_no
                                if max_line is None or line.source_line_no > max_line:
                                    max_line = line.source_line_no

                if min_line is not None and max_line is not None and added_lines:
                    changes.append(CodeChange(
                        file_path=file_path,
                        start_line=min_line,
                        end_line=max_line,
                        change_type=file_change_type,
                        content="".join(added_lines),
                    ))

        return changes

    def get_changed_files(self, repo_root: str, base_branch: str) -> list[CodeChange]:
        """Run git diff against base_branch and parse the result.

        Uses `git diff base_branch` (not `base_branch...HEAD`) so that staged
        and unstaged working-tree changes are included. This matters because
        the developer may call specmap_annotate before committing.
        """
        try:
            result = subprocess.run(
                ["git", "diff", base_branch],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(
                    f"[specmap] Warning: git diff failed: {result.stderr}",
                    file=sys.stderr,
                )
                return []
        except FileNotFoundError:
            print("[specmap] Warning: git not found", file=sys.stderr)
            return []

        return self.parse_diff(result.stdout)

    def get_file_content(self, repo_root: str, file_path: str) -> str | None:
        """Read file content from the repo."""
        full_path = Path(repo_root) / file_path
        try:
            return full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def group_changes(self, changes: list[CodeChange]) -> dict[str, list[CodeChange]]:
        """Group code changes by file path."""
        grouped: dict[str, list[CodeChange]] = {}
        for change in changes:
            grouped.setdefault(change.file_path, []).append(change)
        return grouped
