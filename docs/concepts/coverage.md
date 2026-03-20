# Annotations

Annotations are the core output of Specmap — natural-language descriptions of code regions with `[N]` inline citations linking to spec documents.

## What an Annotation Contains

Each annotation includes:

- **file** -- the code file path
- **start_line / end_line** -- the line range in the code
- **description** -- natural language description with `[N]` spec references inline
- **refs** -- list of spec references, each pointing to a specific heading and excerpt in a spec file

## How Annotations Are Generated

1. **Get changed files** -- `git diff` against the base branch identifies modified code
2. **Read specs** -- markdown spec files are discovered and parsed into sections
3. **LLM annotation** -- code changes and spec sections are sent to the LLM, which generates descriptions with spec citations
4. **Persist** -- annotations are written to `.specmap/{branch}.json`

## Validation

The `specmap validate` CLI command and `specmap_check` MCP tool verify that annotations are structurally valid:

- Referenced files exist in the repo
- Line ranges are within the file's actual line count

This ensures annotations stay in sync with the code as it evolves.
