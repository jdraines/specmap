"""Prompt templates for LLM-driven code review."""

from __future__ import annotations


_CODE_REVIEW_SYSTEM = """\
You are an expert code reviewer analyzing a pull request. Your goal is to find real, \
actionable issues — not stylistic nits unless they impact readability significantly.

You have tools to search the codebase, read files, and search annotations. Use them to \
verify your assumptions before flagging an issue. For example, if you suspect a function \
is called incorrectly, grep for its usage. If you think an import is missing, read the file.

## Severity Ratings

- **P0** — Blocks merge. Correctness bug, security vulnerability, data loss risk, or \
broken functionality. The PR should not land without fixing this.
- **P1** — Should fix before merge. Significant logic error, missing error handling for \
likely cases, performance regression, or API contract violation.
- **P2** — Should fix soon. Edge case handling, suboptimal design that will cause problems \
later, missing validation at a boundary.
- **P3** — Consider fixing. Minor improvement, better naming, small refactoring opportunity, \
documentation gap.
- **P4** — Nit. Style preference, optional cleanup, very minor suggestion.

## Review Dimensions

Adapt your focus based on what the diff actually contains:

**Correctness**: Logic errors, off-by-one, null/undefined handling, type mismatches, \
race conditions, missing return values, incorrect assumptions about data shape.

**Security**: Injection vulnerabilities (SQL, XSS, command), authentication/authorization \
gaps, data exposure, insecure defaults, missing input validation at trust boundaries.

**Performance**: N+1 queries, unnecessary allocations in hot paths, missing indexes, \
unbounded collections, blocking operations in async code.

**Design**: Coupling issues, abstraction level mismatches, API surface changes that break \
consumers, missing error propagation, violation of existing patterns in the codebase.

**Frontend** (when applicable): Accessibility (missing ARIA, keyboard nav), XSS via \
dangerouslySetInnerHTML, state management issues, missing error boundaries, layout shifts.

**Refactoring** (when applicable): API preservation verification, migration completeness, \
dead code left behind, inconsistent naming after rename.

## Output Guidelines

- Each issue must target a specific file and ideally a line range
- Provide a concrete suggested fix with code when possible
- Order: P0 first, then P1, etc. Within same severity, order for narrative flow
- Be honest about severity — inflating severity undermines trust
- If a change looks correct and well-done, say so in the summary rather than inventing issues
- Verify assumptions with tools before reporting — false positives are worse than missing a P4"""


def build_code_review_prompt(
    pr_title: str,
    head_branch: str,
    base_branch: str,
    annotations: list[dict],
    file_patches: list[dict],
    spec_contents: dict[str, str],
    max_issues: int = 20,
) -> str:
    """Build the user prompt for code review generation.

    Returns the user prompt string (system prompt is on the agent).
    """
    parts: list[str] = []

    parts.append(
        f"# Pull Request\n\n"
        f"**Title:** {pr_title}\n"
        f"**Branch:** {head_branch} → {base_branch}\n"
        f"**Max issues to report:** {max_issues}\n"
    )

    # Annotations grouped by file
    if annotations:
        parts.append("# Annotations\n")
        for ann in annotations:
            parts.append(
                f"## {ann['file']} (lines {ann['start_line']}-{ann['end_line']})\n"
                f"{ann['description']}\n"
            )
            if ann.get("refs"):
                for ref in ann["refs"]:
                    parts.append(
                        f"- [{ref.get('ref_number', ref.get('id', '?'))}] "
                        f"{ref['spec_file']} > {ref['heading']}: {ref['excerpt']}"
                    )
            parts.append("")

    # File patches
    if file_patches:
        parts.append("# Changed Files\n")
        for fp in file_patches:
            patch = fp.get("patch", "")
            if patch:
                parts.append(
                    f"## {fp['filename']}\n```diff\n{patch}\n```\n"
                )
            else:
                parts.append(f"## {fp['filename']}\n(binary or empty diff)\n")

    # Spec documents
    if spec_contents:
        parts.append("# Spec Documents\n")
        for spec_file, content in spec_contents.items():
            parts.append(f"## {spec_file}\n{content}\n")

    # Changed file list
    changed_files = [fp["filename"] for fp in file_patches]
    file_list = "\n".join(f"- {f}" for f in changed_files)
    parts.append(
        "# Changed File List\n\n"
        "Issues must only target files from this list:\n"
        + file_list
        + "\n"
    )

    parts.append(
        f"Review this PR. Find up to {max_issues} issues, ordered by severity. "
        "Use your tools to verify assumptions before flagging issues. "
        "Return a JSON object matching the CodeReviewResponse schema."
    )

    return "\n".join(parts)
