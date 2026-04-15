"""Prompt templates for LLM-driven walkthrough generation."""

from __future__ import annotations


_WALKTHROUGH_SYSTEM = """\
You are a code review guide that creates progressive, narrative walkthroughs of pull requests.

Given a PR's annotations, file patches, and spec documents, produce a guided walkthrough that \
helps a reviewer build understanding of the changes step by step.

Guidelines:
- Start with the big picture: what changed and why
- Sequence steps so each builds on prior understanding
- Group related changes even across files — a step targets one file but the narrative can \
reference prior steps
- Highlight key decisions, trade-offs, and non-obvious choices
- Call out assumptions, edge cases, and areas of low confidence
- Use [N] notation to reference spec sections where helpful
- Each step must target a file that appears in the PR's changed file list
- Keep titles short and descriptive (e.g. "Setting up the auth middleware")
- Write narrative in markdown: use **bold**, *italic*, `code`, and [N] spec refs

Adapt to the reviewer's familiarity level:
- Level 1 (unfamiliar): Provide more background, explain domain concepts, define terms
- Level 2 (somewhat familiar): Balanced — explain non-obvious parts, skip basics
- Level 3 (expert): Skip background, focus on decisions, trade-offs, edge cases

Adapt step count to depth:
- "quick": 3-6 steps covering the most important changes
- "thorough": 6-15 steps covering all significant changes in detail

For each step, provide:
- step_number: sequential starting from 1
- title: short heading
- narrative: markdown text with [N] spec refs
- file: target file path (must be in the PR's changed file list)
- start_line / end_line: optional focus range within the file
- refs: list of spec references matching [N] in narrative
- reasoning: brief explanation of your sequencing choice (not stored)

Also provide a 2-3 sentence summary of the entire PR for the walkthrough banner.

Output valid JSON matching the WalkthroughResponse schema."""


def build_walkthrough_prompt(
    pr_title: str,
    head_branch: str,
    base_branch: str,
    annotations: list[dict],
    file_patches: list[dict],
    spec_contents: dict[str, str],
    familiarity: int,
    depth: str,
) -> list[dict]:
    """Build system + user messages for generating a walkthrough.

    Args:
        pr_title: PR title
        head_branch: Source branch name
        base_branch: Target branch name
        annotations: List of annotation dicts grouped by file
        file_patches: List of {filename, patch} dicts
        spec_contents: Dict of spec_file path -> content
        familiarity: 1-3 reviewer familiarity level
        depth: "quick" or "thorough"
    """
    familiarity_label = {1: "unfamiliar", 2: "somewhat familiar", 3: "expert"}.get(
        familiarity, "somewhat familiar"
    )

    # PR metadata
    parts = [
        f"# Pull Request\n\n"
        f"**Title:** {pr_title}\n"
        f"**Branch:** {head_branch} → {base_branch}\n"
        f"**Reviewer familiarity:** {familiarity} ({familiarity_label})\n"
        f"**Depth:** {depth}\n",
    ]

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
                        f"- [{ref.get('ref_number', '?')}] {ref['spec_file']} > "
                        f"{ref['heading']}: {ref['excerpt']}"
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

    # Changed file list for constraining steps
    changed_files = [fp["filename"] for fp in file_patches]
    file_list = "\n".join(f"- {f}" for f in changed_files)
    parts.append(
        "# Changed File List\n\n"
        "Steps must only target files from this list:\n"
        + file_list
        + "\n"
    )

    parts.append(
        "Generate a guided walkthrough for this PR. "
        "Return a JSON object matching the WalkthroughResponse schema."
    )

    return [
        {"role": "system", "content": _WALKTHROUGH_SYSTEM},
        {"role": "user", "content": "\n".join(parts)},
    ]
