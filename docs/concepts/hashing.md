# Hashing & Reindexing

Specmap uses hierarchical content hashing to detect changes efficiently and a multi-strategy relocation system to update mappings without unnecessary LLM calls.

## Hash Format

All hashes use the format:

```
sha256:<first 16 hex characters of SHA-256>
```

For example: `sha256:a1b2c3d4e5f6a7b8`

The 16-character prefix provides sufficient collision resistance for change detection while keeping the specmap file compact.

## Four Hash Levels

Hashes form a hierarchy from coarse to fine:

| Level | What's hashed | Stored in | Purpose |
|---|---|---|---|
| **Document** | Entire spec file content | `spec_documents[path].doc_hash` | Skip unchanged documents |
| **Section** | Content under a heading (to the next heading of same/higher level) | `sections[heading].section_hash` | Skip unchanged sections within a changed document |
| **Span** | Extracted text by offset + length within a section | `spec_spans[].span_hash` | Detect if the specific mapped text changed |
| **Code** | Source code lines (start to end, inclusive, [normalized](#code-hash-normalization)) | `code_target.content_hash` | Detect if the mapped code changed |

## Reindexing Flow

When specs or code change, `specmap_reindex` follows these steps:

1. **Compare document hashes** — for each spec file, re-hash the full content. If the hash matches, skip the entire document (all mappings for this doc are still valid).

2. **Compare section hashes** — within changed documents, re-hash each section. If a section hash matches, skip it.

3. **Relocate spec spans** — for spans in changed sections, attempt to find the text at its new location using the relocation strategies below.

4. **Compare code hashes** — re-hash mapped code regions. If a code hash matches, the code side is unchanged.

5. **Mark stale** — any mapping where both relocation and hash verification fail is marked `stale: true`.

6. **Remap if needed** — mappings that can't be deterministically relocated may be sent to the LLM for re-evaluation.

## Relocation Strategies

When a spec span's hash no longer matches at its recorded offset, the relocator tries three strategies in order:

### 1. Exact at Offset

Check if the text at the original `span_offset` and `span_length` still matches the `span_hash`. This handles the common case where surrounding text changed but the span itself didn't move.

### 2. Exact Match Anywhere

Search the entire section content for an exact match of the original span text. This handles cases where text shifted due to insertions or deletions above it.

### 3. Fuzzy Match

Use Python's `SequenceMatcher` to find the best match in the section with a similarity threshold of **0.8** (80%). This handles minor edits to the span text (typo fixes, rewording) where the intent is preserved.

If all three strategies fail, the mapping is marked stale and may require an LLM call to re-establish.

## Code Hash Normalization

Code hashes strip trailing newlines before hashing. This ensures consistent hashes regardless of whether files end with a trailing newline:

```python
def hash_code_lines(file_content, start_line, end_line):
    lines = file_content.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    selected = lines[start_line - 1 : end_line]
    return hash_content("\n".join(selected))
```

The `split("\n")` → select → `join("\n")` pattern naturally normalizes trailing newlines. This contract is enforced by unit tests and functional tests. See [Development](../development.md#code-hash-normalization) for details.

## Why Hierarchical Hashing?

The hierarchy makes reindexing **proportional to the size of the change**, not the size of the repo:

- A typo fix in one spec section? Only spans in that section are re-checked.
- A new section added to a doc? Only that document is re-indexed; other docs are skipped.
- Code reformatted? Only code hashes for affected regions are re-verified.

This keeps reindexing fast and minimizes LLM costs, since most mappings are relocated deterministically.
