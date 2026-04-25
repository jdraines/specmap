import { apiFetch, apiFetchSSE, apiFetchChatSSE } from './client';
import type { ChatSSECallbacks } from './client';
import type {
  User,
  Repository,
  PullRequest,
  PullFile,
  SpecmapFile,
  SpecContent,
  AuthStatus,
  Walkthrough,
  CodeReview,
  Capabilities,
  GenerateProgress,
  PaginatedResponse,
  CommentsResponse,
  Comment,
  PostCommentRequest,
} from './types';

export const auth = {
  status: () => apiFetch<AuthStatus>('/api/v1/auth/status'),
  me: () => apiFetch<User>('/api/v1/auth/me'),
  logout: () => apiFetch<{ status: string }>('/api/v1/auth/logout', { method: 'POST' }),
  submitToken: (token: string) =>
    apiFetch<{ user: User }>('/api/v1/auth/token', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  saveToken: () =>
    apiFetch<{ saved: boolean; path: string }>('/api/v1/auth/save-token', { method: 'POST' }),
};

export const repos = {
  list: (params?: { page?: number; per_page?: number; search?: string }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.per_page) qs.set('per_page', String(params.per_page));
    if (params?.search) qs.set('search', params.search);
    const query = qs.toString();
    return apiFetch<PaginatedResponse<Repository>>(`/api/v1/repos${query ? `?${query}` : ''}`);
  },
  get: (fullName: string) => apiFetch<Repository>(`/api/v1/repos/${fullName}`),
};

export const pulls = {
  list: (fullName: string) =>
    apiFetch<PullRequest[]>(`/api/v1/repos/${fullName}/pulls`),
  get: (fullName: string, number: number) =>
    apiFetch<PullRequest>(`/api/v1/repos/${fullName}/pulls/${number}`),
  files: (fullName: string, number: number) =>
    apiFetch<PullFile[]>(`/api/v1/repos/${fullName}/pulls/${number}/files`),
  annotations: (fullName: string, number: number) =>
    apiFetch<SpecmapFile>(`/api/v1/repos/${fullName}/pulls/${number}/annotations`),
  fileSource: (fullName: string, number: number, path: string) =>
    apiFetch<{ content: string }>(
      `/api/v1/repos/${fullName}/pulls/${number}/file-source?path=${encodeURIComponent(path)}`,
    ),
  generateAnnotations: (
    fullName: string,
    number: number,
    mode: 'lite' | 'full' = 'full',
    force: boolean = false,
    timeout?: number,
    onProgress?: (data: GenerateProgress) => void,
    resume: boolean = false,
    concurrency: number = 4,
  ) =>
    apiFetchSSE(
      `/api/v1/repos/${fullName}/pulls/${number}/generate-annotations`,
      { mode, force, timeout, resume, concurrency },
      onProgress ?? (() => {}),
      ((timeout ?? 300) * 1000) + 60_000,
    ),
  clearCache: (fullName: string, number: number) =>
    apiFetch<{ status: string }>(
      `/api/v1/repos/${fullName}/pulls/${number}/cache`,
      { method: 'DELETE' },
    ),
};

export const comments = {
  list: (fullName: string, number: number) =>
    apiFetch<CommentsResponse>(`/api/v1/repos/${fullName}/pulls/${number}/comments`),
  post: (fullName: string, number: number, data: PostCommentRequest) =>
    apiFetch<Comment>(`/api/v1/repos/${fullName}/pulls/${number}/comments`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const specs = {
  content: (fullName: string, number: number, path: string) =>
    apiFetch<SpecContent>(`/api/v1/repos/${fullName}/pulls/${number}/specs/${path}`),
};

export const capabilities = {
  get: () => apiFetch<Capabilities>('/api/v1/capabilities'),
};

export const walkthrough = {
  generate: (fullName: string, number: number, familiarity: number, depth: string, timeout: number = 300, signal?: AbortSignal) =>
    apiFetch<Walkthrough>(
      `/api/v1/repos/${fullName}/pulls/${number}/walkthrough`,
      {
        method: 'POST',
        body: JSON.stringify({ familiarity, depth }),
      },
      timeout * 1000 + 60_000,
      signal,
    ),
  chat: (
    fullName: string,
    number: number,
    stepNumber: number,
    message: string,
    familiarity: number,
    depth: string,
    callbacks: ChatSSECallbacks,
  ) =>
    apiFetchChatSSE(
      `/api/v1/repos/${fullName}/pulls/${number}/walkthrough/chat`,
      { step_number: stepNumber, message, familiarity, depth },
      callbacks,
    ),
};

export const codeReview = {
  generate: (fullName: string, number: number, maxIssues: number = 20, timeout: number = 300, signal?: AbortSignal) =>
    apiFetch<CodeReview>(
      `/api/v1/repos/${fullName}/pulls/${number}/code-review`,
      {
        method: 'POST',
        body: JSON.stringify({ max_issues: maxIssues }),
      },
      timeout * 1000 + 60_000,
      signal,
    ),
  chat: (
    fullName: string,
    number: number,
    issueNumber: number,
    message: string,
    callbacks: ChatSSECallbacks,
  ) =>
    apiFetchChatSSE(
      `/api/v1/repos/${fullName}/pulls/${number}/code-review/chat`,
      { issue_number: issueNumber, message },
      callbacks,
    ),
};
