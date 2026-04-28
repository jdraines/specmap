"""Prompt templates for LLM-driven code review."""

from __future__ import annotations


_CODE_REVIEW_SYSTEM = """\
You are an expert code reviewer analyzing a pull request. Your goal is to find real, \
actionable issues — not stylistic nits unless they impact readability significantly.

You have tools to search the codebase, read files, and search annotations. Use them to \
verify your assumptions before flagging an issue.

## Tool Economy

You have a limited tool call budget. Be strategic:
- The full content of all files in your review is included in the prompt. Do NOT use \
read_file for those files — their content is already above.
- The repository file tree is included in the prompt. Do NOT use list_files.
- When you need to read multiple files outside the prompt, pass them ALL in a single \
read_file call using the `paths` parameter.
- Reserve tool calls for verifying cross-boundary issues: checking callers in unchanged \
files, confirming imports, verifying function signatures in other modules.
- Weigh the value of each tool call. If you can answer from the prompt context, do so.

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

**Correctness**: Logic errors, off-by-one, unhandled error paths where no guard exists, \
type mismatches, race conditions, missing return values, incorrect assumptions about data shape.

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

**Cross-codebase wiring**: When you see a changed function signature, renamed export, \
modified type definition, or altered API contract, use grep_codebase to find all callers \
and consumers. Verify they've been updated. If callers exist outside the files you're \
reviewing, flag this as an issue pinned to the primary change, noting the affected \
call sites in the description.

## Self-Verification (Required for P0 and P1)

Before reporting any P0 or P1 issue, you MUST:
1. Quote the exact line(s) containing the problem in your reasoning
2. Trace the code path that leads to the bug — identify what concrete input triggers it
3. Confirm that no guard clause, early return, try/except, or upstream validation \
prevents the issue. Guards may appear as:
   - Early returns: `if not x: return` or `if x is None: return default`
   - Assertions or length checks anywhere before the access
   - Upstream checks in the same function or a calling function
   - Try/except wrapping the access
4. If you cannot construct a concrete triggering input that bypasses ALL existing guards, \
DROP the issue entirely. Do not downgrade it — if the bug doesn't exist, it's not a \
lower-severity bug, it's not a bug at all. Only keep it if you can prove a real trigger.

False P0/P1 issues actively damage reviewer trust. A missed P4 is far better than a false P0.

## Output Guidelines

- Only flag issues on lines that appear in the diff. Do not flag issues on unchanged code \
that is merely visible as context around changes. The reviewer is looking at what changed, \
not a full audit of the existing codebase
- Every issue MUST include start_line and end_line pointing to specific changed lines in the diff. \
Use the diff hunk headers (@@ -old,count +new,count @@) to identify new-file line numbers
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
    custom_prompt: str = "",
    file_contents: dict[str, str] | None = None,
    file_tree: list[str] | None = None,
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

    # File patches + full content
    if file_patches:
        parts.append("# Changed Files\n")
        for fp in file_patches:
            patch = fp.get("patch", "")
            fname = fp["filename"]
            if patch:
                parts.append(f"## {fname}\n### Diff\n```diff\n{patch}\n```\n")
            else:
                parts.append(f"## {fname}\n(binary or empty diff)\n")
            # Include full file content so the agent doesn't need read_file for PR files
            if file_contents and fname in file_contents:
                content = file_contents[fname]
                lines = content.splitlines()
                if len(lines) > 500:
                    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines[:500], 1))
                    parts.append(f"### Full content ({len(lines)} lines, first 500 shown)\n```\n{numbered}\n```\n")
                else:
                    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1))
                    parts.append(f"### Full content ({len(lines)} lines)\n```\n{numbered}\n```\n")

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

    if file_tree:
        tree_text = "\n".join(file_tree[:500])
        truncated = f"\n... and {len(file_tree) - 500} more" if len(file_tree) > 500 else ""
        parts.append(f"# Repository File Tree\n\n```\n{tree_text}{truncated}\n```\n")

    if custom_prompt:
        parts.append(
            "# Reviewer Instructions\n\n"
            "The reviewer has provided additional guidance for this review:\n\n"
            + custom_prompt
            + "\n"
        )

    parts.append(
        f"Review this PR. Find up to {max_issues} issues, ordered by severity. "
        "Use your tools to verify assumptions before flagging issues. "
        "Return a JSON object matching the CodeReviewResponse schema."
    )

    return "\n".join(parts)


def build_chunk_review_prompt(
    pr_title: str,
    head_branch: str,
    base_branch: str,
    chunk_patches: list[dict],
    chunk_index: int,
    total_chunks: int,
    all_changed_files: list[str],
    annotations: list[dict],
    spec_contents: dict[str, str],
    max_issues: int = 20,
    custom_prompt: str = "",
    file_contents: dict[str, str] | None = None,
    file_tree: list[str] | None = None,
) -> str:
    """Build prompt for reviewing a single chunk of a large PR.

    Similar to build_code_review_prompt but adds chunk context and
    emphasizes cross-codebase verification.
    """
    parts: list[str] = []

    chunk_files = [fp["filename"] for fp in chunk_patches]
    other_files = [f for f in all_changed_files if f not in chunk_files]

    parts.append(
        f"# Pull Request (Chunk {chunk_index + 1} of {total_chunks})\n\n"
        f"**Title:** {pr_title}\n"
        f"**Branch:** {head_branch} → {base_branch}\n"
        f"**Max issues to report:** {max_issues}\n\n"
        f"You are reviewing a subset of this PR's changes. "
        f"This chunk contains {len(chunk_files)} file(s). "
        f"The full PR changes {len(all_changed_files)} files total.\n"
    )

    if other_files:
        parts.append(
            "**Other files changed in this PR (not in your chunk):**\n"
            + "\n".join(f"- {f}" for f in other_files[:30])
            + ("\n..." if len(other_files) > 30 else "")
            + "\n\nUse grep_codebase and read_file to check for wiring issues "
            "between your chunk and these other files.\n"
        )

    # Annotations for this chunk's files
    chunk_annotations = [a for a in annotations if a.get("file") in chunk_files]
    if chunk_annotations:
        parts.append("# Annotations\n")
        for ann in chunk_annotations:
            parts.append(
                f"## {ann['file']} (lines {ann['start_line']}-{ann['end_line']})\n"
                f"{ann['description']}\n"
            )
            parts.append("")

    # Chunk file patches
    parts.append("# Changed Files in This Chunk\n")
    for fp in chunk_patches:
        patch = fp.get("patch", "")
        fname = fp["filename"]
        if patch:
            parts.append(f"## {fname}\n### Diff\n```diff\n{patch}\n```\n")
        else:
            parts.append(f"## {fname}\n(binary or empty diff)\n")
        if file_contents and fname in file_contents:
            content = file_contents[fname]
            lines = content.splitlines()
            if len(lines) > 500:
                numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines[:500], 1))
                parts.append(f"### Full content ({len(lines)} lines, first 500 shown)\n```\n{numbered}\n```\n")
            else:
                numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1))
                parts.append(f"### Full content ({len(lines)} lines)\n```\n{numbered}\n```\n")

    # Spec documents
    if spec_contents:
        parts.append("# Spec Documents\n")
        for spec_file, content in spec_contents.items():
            parts.append(f"## {spec_file}\n{content}\n")

    if file_tree:
        tree_text = "\n".join(file_tree[:500])
        truncated = f"\n... and {len(file_tree) - 500} more" if len(file_tree) > 500 else ""
        parts.append(f"# Repository File Tree\n\n```\n{tree_text}{truncated}\n```\n")

    if custom_prompt:
        parts.append(
            "# Reviewer Instructions\n\n" + custom_prompt + "\n"
        )

    parts.append(
        f"Review the files in this chunk. Find up to {max_issues} issues, ordered by severity. "
        "Use your tools to verify assumptions and check for cross-codebase wiring issues. "
        "Return a JSON object matching the CodeReviewResponse schema."
    )

    return "\n".join(parts)


_CONSOLIDATION_SYSTEM = """\
You are a code review consolidator. You receive issues found by multiple review agents \
that each examined a different portion of a pull request. Your job is to:

1. **Merge duplicates**: If two issues describe the same underlying problem (same code, \
same bug, possibly from different perspectives), merge them into one. Pin the issue to the \
primary diff location. Note any cross-codebase contact points in the description.

2. **Validate reasoning**: For every P0 and P1 issue, critically evaluate the reasoning:
   - Does the claimed bug actually exist?
   - Is the reasoning logically consistent? Watch for contradictions like "a guard exists \
but it doesn't work" without a concrete bypass.
   - Could the described triggering input actually reach the flagged code?
   - If the reasoning is flawed or the bug doesn't exist, DROP the issue entirely. \
Do not downgrade — if it's not a real bug, it's not any severity level.

3. **Order results**: P0 first, then P1, etc. Within same severity, order for narrative flow.

4. **Write a summary**: 2-4 sentences covering the overall review findings.

Be skeptical. You are seeing these issues cold — you didn't generate them. False positives \
damage reviewer trust far more than missing a low-severity nit. When in doubt, drop."""


def build_consolidation_prompt(
    issues: list[dict],
    chunk_summaries: list[str],
) -> str:
    """Build prompt for the consolidation agent."""
    parts: list[str] = []

    parts.append(
        f"# Review Consolidation\n\n"
        f"The following {len(issues)} issues were found across "
        f"{len(chunk_summaries)} review chunks.\n"
    )

    if chunk_summaries:
        parts.append("## Chunk Summaries\n")
        for i, summary in enumerate(chunk_summaries):
            parts.append(f"**Chunk {i + 1}:** {summary}\n")

    parts.append("## Issues to Consolidate\n")
    for issue in issues:
        parts.append(
            f"### {issue.get('severity', '?')} — {issue.get('title', '')}\n"
            f"**File:** {issue.get('file', '')} "
            f"(lines {issue.get('start_line', '?')}-{issue.get('end_line', '?')})\n"
            f"**Category:** {issue.get('category', '')}\n"
            f"**Description:** {issue.get('description', '')}\n"
            f"**Reasoning:** {issue.get('reasoning', '')}\n"
            f"**Suggested fix:** {issue.get('suggested_fix', '')}\n"
        )

    parts.append(
        "Consolidate these issues: merge duplicates, validate P0/P1 reasoning "
        "(drop any with flawed logic), and order the result. "
        "Return a JSON object matching the CodeReviewResponse schema."
    )

    return "\n".join(parts)
