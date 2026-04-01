import { apiFetch } from './client';
import type {
  User,
  Repository,
  PullRequest,
  PullFile,
  SpecmapFile,
  SpecContent,
} from './types';

export const auth = {
  me: () => apiFetch<User>('/api/v1/auth/me'),
  logout: () => apiFetch<{ status: string }>('/api/v1/auth/logout', { method: 'POST' }),
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
};

export const specs = {
  content: (owner: string, repo: string, number: number, path: string) =>
    apiFetch<SpecContent>(`/api/v1/repos/${owner}/${repo}/pulls/${number}/specs/${path}`),
};
