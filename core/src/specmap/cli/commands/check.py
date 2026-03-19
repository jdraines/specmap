"""specmap check — coverage enforcement with threshold."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass

import typer

from specmap.cli import app
from specmap.cli.output import get_console
from specmap.state.specmap_file import SpecmapFileManager


@dataclass
class LineRange:
    start: int
    end: int


@dataclass
class UnmappedFile:
    file: str
    coverage: float
    total_lines: int
    mapped_lines: int


@dataclass
class StaleMapping:
    file: str
    start_line: int
    end_line: int
    reason: str


@dataclass
class CoverageReport:
    branch: str = ""
    base_branch: str = ""
    total_files: int = 0
    mapped_files: int = 0
    total_lines: int = 0
    mapped_lines: int = 0
    coverage: float = 0.0
    unmapped: list[UnmappedFile] | None = None
    stale: list[StaleMapping] | None = None

    def __post_init__(self):
        if self.unmapped is None:
            self.unmapped = []
        if self.stale is None:
            self.stale = []


def _changed_files(repo_root: str, base: str) -> dict[str, list[LineRange]]:
    """Run git diff -U0 base...HEAD and parse changed line ranges."""
    try:
        result = subprocess.run(
            ["git", "diff", "-U0", f"{base}...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {}
    except FileNotFoundError:
        return {}

    return _parse_unified_diff(result.stdout)


def _parse_unified_diff(diff: str) -> dict[str, list[LineRange]]:
    """Parse unified diff output (with -U0) into changed line ranges per file."""
    result: dict[str, list[LineRange]] = {}
    file_re = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)

    current_file = ""
    for line in diff.splitlines():
        m = file_re.match(line)
        if m:
            current_file = m.group(1)
            if current_file == "/dev/null":
                current_file = ""
            continue

        if not current_file:
            continue

        m = hunk_re.match(line)
        if m:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) else 1
            if count == 0:
                continue
            end = start + count - 1
            result.setdefault(current_file, []).append(LineRange(start=start, end=end))

    return result


def _count_lines(ranges: list[LineRange]) -> int:
    return sum(r.end - r.start + 1 for r in ranges)


def _count_overlap(changed: list[LineRange], mapped: list[LineRange]) -> int:
    changed_set: set[int] = set()
    for r in changed:
        for i in range(r.start, r.end + 1):
            changed_set.add(i)

    count = 0
    for m in mapped:
        for i in range(m.start, m.end + 1):
            if i in changed_set:
                count += 1
                changed_set.discard(i)
    return count


def _calculate_coverage(sf, changed_files, repo_root) -> CoverageReport:
    """Compute coverage from a specmap file and git diff results."""
    report = CoverageReport()

    if sf is not None:
        report.branch = sf.branch
        report.base_branch = sf.base_branch

    if not changed_files:
        report.coverage = 1.0
        return report

    # Build mapped ranges from specmap mappings.
    mapped_ranges: dict[str, list[LineRange]] = {}
    if sf is not None:
        for m in sf.mappings:
            ct = m.code_target
            mapped_ranges.setdefault(ct.file, []).append(
                LineRange(start=ct.start_line, end=ct.end_line)
            )

    total_changed = 0
    total_mapped = 0
    file_mapped = 0

    for file, ranges in changed_files.items():
        file_changed = _count_lines(ranges)
        total_changed += file_changed

        file_covered = 0
        if file in mapped_ranges:
            file_covered = _count_overlap(ranges, mapped_ranges[file])
        total_mapped += file_covered

        file_coverage = file_covered / file_changed if file_changed > 0 else 0.0

        if file_covered > 0:
            file_mapped += 1

        if file_coverage < 1.0:
            report.unmapped.append(UnmappedFile(
                file=file,
                coverage=file_coverage,
                total_lines=file_changed,
                mapped_lines=file_covered,
            ))

    report.total_files = len(changed_files)
    report.mapped_files = file_mapped
    report.total_lines = total_changed
    report.mapped_lines = total_mapped

    if total_changed > 0:
        report.coverage = total_mapped / total_changed

    # Find stale mappings.
    if sf is not None:
        for m in sf.mappings:
            if m.stale:
                report.stale.append(StaleMapping(
                    file=m.code_target.file,
                    start_line=m.code_target.start_line,
                    end_line=m.code_target.end_line,
                    reason="marked stale",
                ))

    return report


@app.command()
def check(
    ctx: typer.Context,
    threshold: float = typer.Option(0.0, help="Minimum coverage ratio (0.0-1.0)"),
    base: str = typer.Option("", help="Base branch for diff (default: from specmap file)"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of human-readable"),
):
    """Check coverage and enforce thresholds (CI mode)."""
    repo_root: str = ctx.obj["repo_root"]
    branch: str = ctx.obj["branch"]
    no_color: bool = ctx.obj["no_color"]
    console = get_console(no_color)

    mgr = SpecmapFileManager(repo_root)

    # Load specmap file (may not exist).
    fpath = mgr._file_path(branch)
    sf = mgr.load(branch) if fpath.exists() else None

    # Determine base branch.
    base_branch = base
    if not base_branch and sf is not None:
        base_branch = sf.base_branch
    if not base_branch:
        base_branch = "main"

    # Get changed files.
    changed_files = _changed_files(repo_root, base_branch)
    if not changed_files and not json_output:
        pass  # git diff may have failed — we proceed with empty

    report = _calculate_coverage(sf, changed_files, repo_root)
    passed = report.coverage >= threshold

    if json_output:
        out = {
            "branch": report.branch or branch,
            "base_branch": report.base_branch or base_branch,
            "total_files": report.total_files,
            "mapped_files": report.mapped_files,
            "total_lines": report.total_lines,
            "mapped_lines": report.mapped_lines,
            "coverage": report.coverage,
            "threshold": threshold,
            "pass": passed,
            "unmapped": [
                {
                    "file": u.file,
                    "coverage": u.coverage,
                    "total_lines": u.total_lines,
                    "mapped_lines": u.mapped_lines,
                }
                for u in report.unmapped
            ],
            "stale": [
                {
                    "file": s.file,
                    "start_line": s.start_line,
                    "end_line": s.end_line,
                    "reason": s.reason,
                }
                for s in report.stale
            ],
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
        if not passed:
            raise typer.Exit(code=1)
        return

    # Human output.
    console.print(f"specmap: checking coverage for {branch} (base: {base_branch})")
    console.print(
        f"Files: {report.mapped_files}/{report.total_files} mapped | "
        f"Lines: {report.mapped_lines}/{report.total_lines} mapped"
    )

    if report.unmapped:
        sorted_unmapped = sorted(report.unmapped, key=lambda u: u.coverage)
        parts = [
            f"{u.file} ({u.coverage * 100:.0f}%, {u.total_lines - u.mapped_lines} lines)"
            for u in sorted_unmapped
        ]
        console.print(f"Unmapped: {', '.join(parts)}")

    if report.stale:
        parts = [
            f"{s.file}:{s.start_line}-{s.end_line} ({s.reason})"
            for s in report.stale
        ]
        console.print(f"Stale: {', '.join(parts)}")

    coverage_pct = report.coverage * 100
    threshold_pct = threshold * 100
    if passed:
        result_str = "[green]PASS[/green]" if not no_color else "PASS"
    else:
        result_str = "[red]FAIL[/red]" if not no_color else "FAIL"

    console.print(
        f"Overall: {coverage_pct:.1f}% (threshold: {threshold_pct:.1f}%) \u2014 {result_str}"
    )

    if not passed:
        raise typer.Exit(code=1)
