import type { ChatMessage, GenerateProgress, SpecmapFile } from './types';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  timeout: number = 30_000,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  // Link caller's signal to our controller so either can abort
  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const resp = await fetch(path, {
      credentials: 'include',
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    });

    if (resp.status === 401) {
      // Redirect to app root — the app router shows login/setup based on auth status
      window.location.href = '/';
      throw new ApiError(401, 'Unauthorized');
    }

    if (!resp.ok) {
      const body = await resp.text();
      throw new ApiError(resp.status, body);
    }

    return resp.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

export async function apiFetchSSE(
  path: string,
  body: unknown,
  onProgress: (data: GenerateProgress) => void,
  timeout: number = 180_000,
): Promise<SpecmapFile> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(path, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (resp.status === 401) {
      window.location.href = '/';
      throw new ApiError(401, 'Unauthorized');
    }

    if (!resp.ok) {
      const text = await resp.text();
      throw new ApiError(resp.status, text);
    }

    // If response is JSON (cache hit), return directly
    const contentType = resp.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
      return (await resp.json()) as SpecmapFile;
    }

    // Parse SSE stream
    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result: SpecmapFile | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop()!;

      for (const part of parts) {
        if (!part.trim()) continue;
        let eventType = 'message';
        let data = '';

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7);
          } else if (line.startsWith('data: ')) {
            data = line.slice(6);
          }
        }

        if (!data) continue;
        const parsed = JSON.parse(data);

        if (eventType === 'progress') {
          onProgress(parsed as GenerateProgress);
        } else if (eventType === 'complete') {
          result = parsed as SpecmapFile;
        } else if (eventType === 'error') {
          throw new ApiError(500, parsed.message ?? 'Generation failed');
        }
      }
    }

    if (!result) {
      throw new ApiError(500, 'SSE stream ended without a complete event');
    }
    return result;
  } finally {
    clearTimeout(timer);
  }
}

export interface ChatSSECallbacks {
  onDelta: (content: string) => void;
  onToolCall: (tool: string, args: unknown) => void;
  onToolResult: (tool: string, summary: string) => void;
  onDone: (message: ChatMessage) => void;
  onError?: (message: string) => void;
}

export async function apiFetchChatSSE(
  path: string,
  body: unknown,
  callbacks: ChatSSECallbacks,
  timeout: number = 300_000,
): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(path, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (resp.status === 401) {
      window.location.href = '/';
      throw new ApiError(401, 'Unauthorized');
    }

    if (!resp.ok) {
      const text = await resp.text();
      throw new ApiError(resp.status, text);
    }

    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop()!;

      for (const part of parts) {
        if (!part.trim()) continue;
        let eventType = 'message';
        let data = '';

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7);
          } else if (line.startsWith('data: ')) {
            data = line.slice(6);
          }
        }

        if (!data) continue;
        const parsed = JSON.parse(data);

        if (eventType === 'delta') {
          callbacks.onDelta(parsed.content);
        } else if (eventType === 'tool_call') {
          callbacks.onToolCall(parsed.tool, parsed.args);
        } else if (eventType === 'tool_result') {
          callbacks.onToolResult(parsed.tool, parsed.summary);
        } else if (eventType === 'done') {
          callbacks.onDone(parsed.message as ChatMessage);
        } else if (eventType === 'error') {
          callbacks.onError?.(parsed.message ?? 'Chat failed');
        }
      }
    }
  } finally {
    clearTimeout(timer);
  }
}
