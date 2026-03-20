# MCP Server Overview

The Specmap MCP server bridges coding agents to the specmap system via the [Model Context Protocol](https://modelcontextprotocol.io/) stdio transport. It runs alongside your coding agent and provides three tools for generating, validating, and querying spec-to-code annotations.

## What It Does

When a coding agent writes or modifies code, the MCP server:

1. **Detects** the repo root, branch, and spec files automatically
2. **Analyzes** code diffs against the base branch (or incrementally from the last `head_sha`)
3. **Annotates** code changes using an LLM, generating natural-language descriptions with `[N]` spec citations
4. **Persists** annotations to `.specmap/{branch}.json`

## Tools at a Glance

| Tool | Purpose | Makes LLM calls? |
|---|---|---|
| [`specmap_annotate`](tools.md#specmap_annotate) | Generate annotations with spec references for code changes | Yes |
| [`specmap_check`](tools.md#specmap_check) | Verify existing annotations have valid line ranges | No |
| [`specmap_unmapped`](tools.md#specmap_unmapped) | Find code changes without spec coverage | No |

## BYOK -- Bring Your Own Key

The MCP server never bundles or requires a specific LLM provider. It uses [litellm](https://docs.litellm.ai/) to support any provider:

- OpenAI, Anthropic, Google, Mistral, Cohere, and more
- Azure OpenAI, AWS Bedrock, Google Vertex
- Local models via Ollama or vLLM

Configure your provider with `SPECMAP_MODEL`, `SPECMAP_API_KEY`, and optionally `SPECMAP_API_BASE`. See [Configuration](../getting-started/configuration.md) for details.

## Auto-Detection

All tool parameters are optional. The server auto-detects:

- **Repo root** -- walks up from the working directory looking for `.git/`
- **Branch** -- reads from `git rev-parse --abbrev-ref HEAD`
- **Spec files** -- globs `**/*.md` (configurable) with smart exclusions
- **Code changes** -- runs `git diff` against the base branch (or incrementally from `head_sha`)
