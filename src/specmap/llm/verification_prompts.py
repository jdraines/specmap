"""Prompt templates for false-positive verification of code review issues."""

from __future__ import annotations


_VERIFICATION_SYSTEM = """\
You are a false-positive verification agent for an automated code review pipeline. \
You receive a single code review issue flagged by a prior review agent. Your job is \
to determine whether the issue is real by examining the actual code with your tools.

For each issue:
1. Read the flagged file and lines to see the actual code in context.
2. Check for guard clauses, error handling, type checks, upstream validation, or other \
defenses the original reviewer may have missed.
3. If the issue references cross-file concerns (e.g. callers not updated, stale imports), \
grep the codebase to verify.
4. Search annotations for spec context if the issue relates to spec compliance.

Render one of three verdicts:

- **confirmed**: The issue is real and the severity is appropriate. The code path the \
reviewer described can actually be triggered, and no existing guard prevents it.
- **false_positive**: The issue does not exist. A guard clause, type constraint, upstream \
validation, or framework guarantee prevents the described problem. Explain specifically \
what evidence disproves it.
- **downgrade**: The issue exists but the severity is inflated. Set updated_severity to \
the correct level and explain why.

Be thorough but efficient — you have a limited tool budget. Focus your tool calls on \
the specific claims made in the issue description. Do not invent new issues; your only \
job is to verify or refute the one issue presented.

Output valid JSON matching the VerificationResult schema."""


def build_verification_prompt(
    issue: dict,
    file_patch: str | None,
    pr_title: str,
    changed_files: list[str],
) -> str:
    """Build the user prompt for verifying a single code review issue.

    Args:
        issue: Dict with severity, title, description, file, start_line, end_line,
               reasoning, suggested_fix, category.
        file_patch: The diff patch for the issue's file (if available).
        pr_title: PR title for context.
        changed_files: List of all changed file paths in the PR.
    """
    parts: list[str] = []

    parts.append(
        f"# Issue to Verify\n\n"
        f"**Severity:** {issue.get('severity', '?')}\n"
        f"**Title:** {issue.get('title', '')}\n"
        f"**File:** {issue.get('file', '')}\n"
        f"**Lines:** {issue.get('start_line', '?')}-{issue.get('end_line', '?')}\n"
        f"**Category:** {issue.get('category', '')}\n\n"
        f"**Description:**\n{issue.get('description', '')}\n"
    )

    if issue.get("reasoning"):
        parts.append(f"**Reviewer's reasoning:**\n{issue['reasoning']}\n")

    if issue.get("suggested_fix"):
        parts.append(f"**Suggested fix:**\n{issue['suggested_fix']}\n")

    if file_patch:
        parts.append(f"# Diff for {issue.get('file', '')}\n\n```diff\n{file_patch}\n```\n")

    parts.append(
        f"# PR Context\n\n"
        f"**Title:** {pr_title}\n"
        f"**Changed files:** {', '.join(changed_files[:30])}"
    )
    if len(changed_files) > 30:
        parts.append(f" ... and {len(changed_files) - 30} more")
    parts.append("\n")

    parts.append(
        "Verify this issue. Use your tools to read the actual code, check for guards, "
        "and grep for cross-file references as needed. "
        "Return a JSON object matching the VerificationResult schema."
    )

    return "\n".join(parts)
