import { apiFetch } from './client';
import type {
  User,
  Repository,
  PullRequest,
  PullFile,
  SpecmapFile,
  SpecContent,
  AuthStatus,
  Walkthrough,
  Capabilities,
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
};

export const repos = {
  list: () => apiFetch<Repository[]>('/api/v1/repos'),
  get: (owner: string, repo: string) => apiFetch<Repository>(`/api/v1/repos/${owner}/${repo}`),
};

export const pulls = {
  list: (owner: string, repo: string) =>
    apiFetch<PullRequest[]>(`/api/v1/repos/${owner}/${repo}/pulls`),
  get: (owner: string, repo: string, number: number) =>
    apiFetch<PullRequest>(`/api/v1/repos/${owner}/${repo}/pulls/${number}`),
  files: (owner: string, repo: string, number: number) =>
    apiFetch<PullFile[]>(`/api/v1/repos/${owner}/${repo}/pulls/${number}/files`),
  annotations: (owner: string, repo: string, number: number) =>
    apiFetch<SpecmapFile>(`/api/v1/repos/${owner}/${repo}/pulls/${number}/annotations`),
  fileSource: (owner: string, repo: string, number: number, path: string) =>
    apiFetch<{ content: string }>(
      `/api/v1/repos/${owner}/${repo}/pulls/${number}/file-source?path=${encodeURIComponent(path)}`,
    ),
  generateAnnotations: (
    owner: string,
    repo: string,
    number: number,
    mode: 'lite' | 'full' = 'full',
    force: boolean = false,
  ) =>
    apiFetch<SpecmapFile>(
      `/api/v1/repos/${owner}/${repo}/pulls/${number}/generate-annotations`,
      {
        method: 'POST',
        body: JSON.stringify({ mode, force }),
      },
      180_000,
    ),
  clearCache: (owner: string, repo: string, number: number) =>
    apiFetch<{ status: string }>(
      `/api/v1/repos/${owner}/${repo}/pulls/${number}/cache`,
      { method: 'DELETE' },
    ),
};

export const specs = {
  content: (owner: string, repo: string, number: number, path: string) =>
    apiFetch<SpecContent>(`/api/v1/repos/${owner}/${repo}/pulls/${number}/specs/${path}`),
};

export const capabilities = {
  get: () => apiFetch<Capabilities>('/api/v1/capabilities'),
};

export const walkthrough = {
  generate: (owner: string, repo: string, number: number, familiarity: number, depth: string) =>
    apiFetch<Walkthrough>(
      `/api/v1/repos/${owner}/${repo}/pulls/${number}/walkthrough`,
      {
        method: 'POST',
        body: JSON.stringify({ familiarity, depth }),
      },
      120_000,
    ),
};
