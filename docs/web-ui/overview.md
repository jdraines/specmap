# Web UI Overview

The specmap web UI is a React single-page application served by the `specmap serve` command. It lets you browse repositories and pull requests with spec annotations overlaid on diffs, generate AI-powered walkthroughs and code reviews, and chat with an AI assistant about the changes.

## Getting Started

```bash
pip install specmap    # or: uv tool install specmap
specmap serve
```

The server starts on port 8080 (auto-increments if busy) and opens your browser automatically. On first run, if no LLM API key is configured, you'll be prompted to enter one interactively.

To suppress the browser auto-open:

```bash
specmap serve --no-open
```

See [Configuration](../getting-started/configuration.md) for LLM provider setup and [`specmap serve`](../cli/commands.md#serve) for all server flags.

## Authentication

Specmap needs a forge token (GitHub or GitLab) to fetch repository data. The forge provider is auto-detected from `git remote origin`.

### PAT mode (default)

Set a personal access token via any of these methods:

**GitHub:**

1. `GITHUB_TOKEN` or `GH_TOKEN` environment variable
2. `gh` CLI authenticated (`gh auth login`)
3. Enter manually in the web UI login page

**GitLab:**

1. `GITLAB_TOKEN` environment variable
2. `glab` CLI authenticated
3. Enter manually in the web UI login page

### OAuth mode

For organizations that restrict PATs, configure OAuth credentials. See [Production Deployment](../deployment/production.md#auth-configuration) for setup details.

## Dashboard

After authenticating, the dashboard shows your repositories with recent PRs. Features:

- **Search** -- full-text search across repository names
- **Pagination** -- 20 repos per page
- **Recent PRs** -- each repo shows its latest open PRs for quick access
- **Local repo detection** -- if the server is running inside a git repo, it auto-redirects to that repo's PR list

Click a repository to see its pull requests, then click a PR to open the review page.

## PR Review Page

The review page is the core of the web UI. It combines a diff viewer with AI-powered annotation, walkthrough, and code review features.

### Diff Viewer

- **Layout modes** -- toggle between inline and side-by-side layout in the toolbar
- **Syntax highlighting** -- diffs rendered with language-aware highlighting
- **Hunk expansion** -- click the expansion button between hunks to reveal hidden context lines
- **File tree sidebar** -- collapsible sidebar listing all changed files

### Annotation Widgets

When annotations exist for a PR, they appear as inline widgets in the diff:

- **Blue cards** showing natural-language descriptions of what each code region does
- **`[N]` citation badges** -- clickable references to spec documents. Hover for a tooltip with the heading and excerpt; click to open the spec panel
- **Spec panel** -- side panel showing the full spec file content, scrolled to the cited section
- **Hover cross-highlighting** -- hovering an annotation highlights its code lines, and vice versa
- **Annotation minimap** -- colored dots along the right edge of the viewport for quick navigation

### PR Comments

The review page displays PR comment threads from GitHub/GitLab:

- **Line-level comments** -- rendered inline in the diff at the commented line
- **General comments** -- shown in a conversation panel above the diff
- **Reactions** -- emoji reaction counts on each comment
- **Polling** -- comments refresh automatically every 60 seconds

### Keyboard Shortcuts

Press `?` to open the shortcut help overlay. Key bindings include:

| Key | Action |
|-----|--------|
| `j` / `k` | Next / previous file |
| `n` / `p` | Next / previous annotation |
| `o` | Collapse / expand file |
| `t` | Toggle theme |
| `Esc` | Close panels |

### Theme

Toggle between light, dark, and system-default themes using the theme button in the toolbar.

## AI Features

The web UI provides three AI-powered features, each available from the PR review page toolbar. All require an LLM API key to be configured.

- **[Generate Annotations](generating-annotations.md)** -- create spec-linked annotations for the PR's changes
- **[Guided Walkthroughs](walkthroughs.md)** -- AI-generated narrative tour of the PR, step by step
- **[Code Review](code-review.md)** -- AI-powered code review with structured issues and severity ratings
