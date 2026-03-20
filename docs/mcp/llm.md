# LLM Integration

Specmap uses LLM calls to generate annotations -- natural-language descriptions of code regions with inline spec citations. The MCP server wraps [litellm](https://docs.litellm.ai/) for provider-agnostic model access.

## BYOK via litellm

Specmap supports any provider that litellm supports:

| Provider | Model example | Notes |
|---|---|---|
| OpenAI | `gpt-4o-mini` (default) | Direct API |
| Anthropic | `claude-sonnet-4-20250514` | Direct API |
| Azure OpenAI | `azure/gpt-4o-mini` | Set `SPECMAP_API_BASE` |
| AWS Bedrock | `bedrock/anthropic.claude-3-haiku` | Uses AWS credentials |
| Google Vertex | `vertex_ai/gemini-pro` | Uses GCP credentials |
| Ollama (local) | `ollama/llama3` | Set `SPECMAP_API_BASE` to `http://localhost:11434` |

See [Configuration](../getting-started/configuration.md) for setup details.

## Model Configuration

Set the model via environment variable or config file:

```bash
# Environment variable (takes precedence)
export SPECMAP_MODEL="gpt-4o-mini"

# Or in .specmap/config.json
{"model": "gpt-4o-mini"}
```

## Token Tracking

Every `specmap_annotate` response includes LLM usage metrics:

```json
{
  "llm_usage": {
    "total_input_tokens": 2450,
    "total_output_tokens": 380,
    "total_calls": 2
  }
}
```

This helps you monitor costs. The server accumulates token counts across all LLM calls within a single tool invocation.

## Retry Behavior

The LLM client uses exponential backoff for transient errors:

- **Max retries:** 3 attempts
- **Retried errors:** rate limits (429), service unavailable (503)
- Non-retryable errors (auth, bad request) fail immediately

## Structured Output

LLM responses are parsed into Pydantic models for reliability:

- **`AnnotationResponse`** -- used by `specmap_annotate` to get a list of annotations, each with a natural-language description and `[N]` spec citations pointing to specific spec file locations

If the LLM returns invalid JSON, the call is retried.

## Cost Optimization

Specmap minimizes LLM calls through diff-based optimization:

1. **First push** -- `git diff base_branch...HEAD` produces the full diff; the LLM annotates all changed code
2. **Subsequent pushes** -- `git diff {head_sha}..HEAD` produces an incremental diff; existing annotations are classified:
   - **Keep** -- annotation not affected by the incremental diff
   - **Shift** -- annotation's line numbers adjusted mechanically (no LLM call)
   - **Regenerate** -- annotation overlaps with changed hunks; sent to LLM

Most annotations on subsequent pushes are either kept or shifted without any LLM involvement, keeping costs proportional to the incremental change size.
