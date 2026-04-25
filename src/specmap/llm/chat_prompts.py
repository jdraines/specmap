"""Prompt builder for walkthrough step chat."""

from __future__ import annotations

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart


def build_chat_messages(
    pr_title: str,
    head_branch: str,
    base_branch: str,
    steps: list[dict],
    current_step_number: int,
    file_patch: str | None,
    file_source: str | None,
    chat_history: list[dict],
) -> list[ModelMessage]:
    """Build the message history for the chat agent.

    Args:
        pr_title: PR title.
        head_branch: Source branch.
        base_branch: Target branch.
        steps: All walkthrough steps as dicts.
        current_step_number: 1-indexed step number the user is viewing.
        file_patch: Diff patch for the current step's file (or None).
        file_source: Source code excerpt for the current step's file (or None).
        chat_history: List of {"role": "user"|"assistant", "content": str} dicts.

    Returns:
        List of ModelMessage objects for pydantic-ai.
    """
    # Build the context block
    parts: list[str] = []

    parts.append(
        f"## PR Overview\n"
        f"**Title:** {pr_title}\n"
        f"**Branch:** {head_branch} → {base_branch}\n"
    )

    # Full walkthrough with truncation for non-current steps
    parts.append("## Full Walkthrough\n")
    for step in steps:
        sn = step.get("step_number", 0)
        title = step.get("title", "")
        narrative = step.get("narrative", "")
        file = step.get("file", "")

        if sn == current_step_number:
            label = "CURRENT STEP"
            text = narrative
        elif sn < current_step_number:
            label = "seen by reviewer"
            text = narrative[:200] + ("..." if len(narrative) > 200 else "")
        else:
            label = "not yet seen"
            text = narrative[:200] + ("..." if len(narrative) > 200 else "")

        parts.append(
            f"**Step {sn}: {title}** [{file}] ← {label}\n{text}\n"
        )

    parts.append(
        f"Note: The reviewer is currently on Step {current_step_number}. "
        f"They have seen Steps 1-{current_step_number}. "
        f"Later steps may not have been seen yet — avoid spoiling unless asked.\n"
    )

    # Current step details
    current = next(
        (s for s in steps if s.get("step_number") == current_step_number),
        None,
    )
    if current:
        parts.append("## Current Step Details\n")
        parts.append(f"**Title:** {current.get('title', '')}")
        f = current.get("file", "")
        sl = current.get("start_line", 0)
        el = current.get("end_line", 0)
        if f:
            loc = f"**File:** {f}"
            if sl and el:
                loc += f" (lines {sl}-{el})"
            parts.append(loc)
        parts.append(f"**Narrative:** {current.get('narrative', '')}")

        refs = current.get("refs", [])
        if refs:
            ref_lines = []
            for ref in refs:
                ref_lines.append(
                    f"- [{ref.get('id', '?')}] {ref.get('spec_file', '')} > "
                    f"{ref.get('heading', '')}: {ref.get('excerpt', '')}"
                )
            parts.append("**Spec References:**\n" + "\n".join(ref_lines))

    # File context for the current step
    if file_patch or file_source:
        parts.append("## Current Step File Context\n")
        if file_patch:
            parts.append(f"### Diff\n```diff\n{file_patch}\n```\n")
        if file_source:
            parts.append(f"### Source\n```\n{file_source}\n```\n")

    context_text = "\n".join(parts)

    # Build message list: context as first user message, then chat history
    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content=context_text)]),
        ModelResponse(parts=[TextPart(
            content="I've reviewed the walkthrough context. Feel free to ask me anything about this step or the PR."
        )]),
    ]

    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(
                ModelRequest(parts=[UserPromptPart(content=msg["content"])])
            )
        elif msg["role"] == "assistant":
            messages.append(
                ModelResponse(parts=[TextPart(content=msg["content"])])
            )

    return messages
