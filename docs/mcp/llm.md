# LLM Integration

Specmap uses LLM calls to understand the semantic relationship between spec text and code. The MCP server wraps [litellm](https://docs.litellm.ai/) for provider-agnostic model access.

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

Every `specmap_map` response includes LLM usage metrics:

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

- **`MappingResponse`** — used by `specmap_map` to get a list of spec-to-code mappings with relevance scores and reasoning
- **`ReindexResult`** — used by `specmap_reindex` to determine if a mapping can be relocated in updated content

If the LLM returns invalid JSON, the call is retried.

## Cost Optimization

Specmap minimizes LLM calls through hierarchical hashing:

1. **Document hash** — if unchanged, skip the entire document
2. **Section hash** — if unchanged, skip sections within a changed document
3. **Span hash** — if unchanged, skip individual spans within a changed section
4. **Code hash** — if the mapped code region is unchanged, skip the mapping entirely

During reindexing, Specmap first tries deterministic relocation strategies (exact offset, exact match anywhere, fuzzy match) before falling back to an LLM call. Most mappings are relocated without any LLM involvement.
