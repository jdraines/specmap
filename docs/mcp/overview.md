# MCP Server Overview

The Specmap MCP server bridges coding agents to the specmap system via the [Model Context Protocol](https://modelcontextprotocol.io/) stdio transport. It runs alongside your coding agent and provides four tools for creating, validating, and maintaining spec-to-code mappings.

## What It Does

When a coding agent writes or modifies code, the MCP server:

1. **Detects** the repo root, branch, and spec files automatically
2. **Parses** spec documents into a hierarchy of sections with content hashes
3. **Analyzes** code diffs against the base branch
4. **Maps** code changes to spec spans using an LLM (your key, your model)
5. **Persists** mappings to `.specmap/{branch}.json` — hashes and pointers only, never raw text

## Tools at a Glance

| Tool | Purpose | Makes LLM calls? |
|---|---|---|
| [`specmap_map`](tools.md#specmap_map) | Map code changes to spec sections | Yes |
| [`specmap_check`](tools.md#specmap_check) | Verify existing mappings are still valid | No |
| [`specmap_unmapped`](tools.md#specmap_unmapped) | Find code changes without spec coverage | No |
| [`specmap_reindex`](tools.md#specmap_reindex) | Re-locate mappings after specs or code shift | Yes (when fuzzy matching) |

## BYOK — Bring Your Own Key

The MCP server never bundles or requires a specific LLM provider. It uses [litellm](https://docs.litellm.ai/) to support any provider:

- OpenAI, Anthropic, Google, Mistral, Cohere, and more
- Azure OpenAI, AWS Bedrock, Google Vertex
- Local models via Ollama or vLLM

Configure your provider with `SPECMAP_MODEL`, `SPECMAP_API_KEY`, and optionally `SPECMAP_API_BASE`. See [Configuration](../getting-started/configuration.md) for details.

## Auto-Detection

All tool parameters are optional. The server auto-detects:

- **Repo root** — walks up from the working directory looking for `.git/`
- **Branch** — reads from `git rev-parse --abbrev-ref HEAD`
- **Spec files** — globs `**/*.md` (configurable) with smart exclusions
- **Code changes** — runs `git diff` against the base branch
