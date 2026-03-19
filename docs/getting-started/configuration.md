# Configuration

Specmap loads configuration from two sources. Environment variables take precedence over the config file.

## Config Sources

| Priority | Source | Location |
|---|---|---|
| 1 (highest) | Environment variables | Shell environment |
| 2 | Config file | `.specmap/config.json` in repo root |
| 3 | Defaults | Built into the MCP server |

## All Options

| Environment Variable | Config Key | Default | Description |
|---|---|---|---|
| `SPECMAP_MODEL` | `model` | `gpt-4o-mini` | LLM model identifier (any litellm-supported model) |
| `SPECMAP_API_KEY` | `api_key` | — | API key for LLM provider (required) |
| `SPECMAP_API_BASE` | `api_base` | — | Custom API base URL (for proxies, local models) |
| `SPECMAP_SPEC_PATTERNS` | `spec_patterns` | `**/*.md` | Comma-separated glob patterns for spec files |
| `SPECMAP_IGNORE_PATTERNS` | `ignore_patterns` | `*.generated.go,*.lock,vendor/**` | Comma-separated patterns for files to ignore |

## Config File Format

```json
{
  "model": "gpt-4o-mini",
  "api_key": "sk-...",
  "api_base": null,
  "spec_patterns": ["**/*.md"],
  "ignore_patterns": ["*.generated.go", "*.lock", "vendor/**"]
}
```

!!! danger "Security: never commit config.json"
    `.specmap/config.json` may contain your API key. It is already in `.gitignore` by default. The MCP server warns to stderr if it detects this file is tracked by git.

## Spec Auto-Discovery

When using the default `**/*.md` pattern, Specmap automatically excludes common non-spec files:

**Excluded filenames:**

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `LICENSE.md`
- `CODE_OF_CONDUCT.md`

**Excluded directories:**

- `node_modules`
- `.git`
- `.specmap`
- `vendor`
- `__pycache__`
- `.venv` / `venv`

To override these defaults, set `SPECMAP_SPEC_PATTERNS` to explicit patterns:

```bash
export SPECMAP_SPEC_PATTERNS="docs/**/*.md,specs/**/*.md"
```

## Examples

### Use Anthropic Claude

```bash
export SPECMAP_MODEL="claude-sonnet-4-20250514"
export SPECMAP_API_KEY="sk-ant-..."
```

### Use a Local Model (via Ollama)

```bash
export SPECMAP_MODEL="ollama/llama3"
export SPECMAP_API_BASE="http://localhost:11434"
```

### Use Azure OpenAI

```bash
export SPECMAP_MODEL="azure/gpt-4o-mini"
export SPECMAP_API_KEY="your-azure-key"
export SPECMAP_API_BASE="https://your-resource.openai.azure.com"
```
