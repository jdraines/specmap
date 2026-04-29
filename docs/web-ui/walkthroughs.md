# Guided Walkthroughs

Walkthroughs are AI-generated narrative tours of a pull request. Instead of reading a flat diff file by file, a walkthrough guides you through the changes step by step, building understanding progressively -- starting with the big picture and then diving into the details.

## Generating a Walkthrough

Open a PR in the web UI, then click **Walkthrough** in the toolbar. Configure two parameters:

### Familiarity Level

How well the reviewer knows the codebase:

| Level | Description | Effect |
|-------|-------------|--------|
| 1 | Unfamiliar | More background, domain concepts explained, terms defined |
| 2 | Somewhat familiar | Balanced -- explains non-obvious parts, skips basics |
| 3 | Expert | Skips background, focuses on decisions, trade-offs, edge cases |

### Depth

How many steps the walkthrough should cover:

| Depth | Steps | Description |
|-------|-------|-------------|
| Quick | 3-6 | Covers the most important changes |
| Thorough | 6-15 | Covers all significant changes in detail |

Click **Generate** to start. Progress streams in real-time as the LLM processes the PR's annotations, file patches, and spec documents.

## Reading a Walkthrough

Each walkthrough consists of:

- **Summary** -- a 2-3 sentence overview of the entire PR displayed in the banner
- **Steps** -- sequential cards, each targeting a specific file and (optionally) a line range

Each step includes:

- **Title** -- short heading (e.g., "Setting up the auth middleware")
- **Narrative** -- markdown text explaining what the code does, why, and how it connects to previous steps. Uses `[N]` references to link to spec sections
- **File and line range** -- the specific code region the step discusses. Clicking the step scrolls the diff to that location
- **Spec references** -- clickable `[N]` badges that open the spec panel

### Navigation

Navigate between steps using:

- The step list in the walkthrough panel
- Arrow keys or `[` / `]` bracket keys
- Clicking directly on a step card

Steps are sequenced so each builds on the understanding from previous steps. Related changes are grouped even across files.

## Per-Step Chat

At each step, you can ask questions using the chat input. The chat agent has access to tools for investigating the codebase:

| Tool | Description |
|------|-------------|
| `search_annotations` | Search PR annotations by keyword and file pattern |
| `grep_codebase` | Regex search across files in the repo |
| `list_files` | Browse the repository file tree |
| `read_file` | Read file content with optional line range, includes diff for changed files |

The agent uses these tools proactively to verify claims rather than speculating. Responses are streamed in real-time, and tool calls are visible in the chat.

## Variant Caching

Walkthroughs are cached by PR + head SHA + familiarity + depth. Generating a new walkthrough with different settings creates a separate variant. You can switch between cached variants without regenerating.

If the PR is updated (new commits pushed), the cache is invalidated and a fresh walkthrough can be generated.
