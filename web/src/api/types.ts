export interface User {
  id: number;
  provider: string;
  provider_id: number;
  login: string;
  name: string;
  avatar_url: string;
  created_at: string;
  updated_at: string;
}

export interface Repository {
  id: number;
  provider: string;
  provider_id: number;
  owner: string;
  name: string;
  full_name: string;
  private: boolean;
  created_at: string;
  updated_at: string;
  recent_pulls?: PullRequest[];
}

export interface PullRequest {
  id: number;
  repository_id: number;
  number: number;
  title: string;
  state: string;
  head_branch: string;
  base_branch: string;
  head_sha: string;
  author_login: string;
  created_at: string;
  updated_at: string;
}

export interface PullFile {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  patch: string;
}

export interface SpecRef {
  id: number;
  spec_file: string;
  heading: string;
  start_line: number;
  excerpt: string;
}

export interface Annotation {
  id: string;
  file: string;
  start_line: number;
  end_line: number;
  description: string;
  refs: SpecRef[];
  created_at: string;
}

export interface SpecmapFile {
  version: number;
  branch: string;
  base_branch: string;
  head_sha: string;
  updated_at: string;
  updated_by: string;
  annotations: Annotation[];
  ignore_patterns: string[];
  partial?: boolean;
  completed_batches?: number;
  total_batches?: number;
}

export interface SpecContent {
  path: string;
  content: string;
}

export interface AuthStatus {
  authenticated: boolean;
  auth_mode: 'pat' | 'oauth';
  provider: string;
  user?: User;
  setup_hint?: string;
  current_repo?: string;
}

export interface WalkthroughStep {
  step_number: number;
  title: string;
  narrative: string;
  file: string;
  start_line: number | null;
  end_line: number | null;
  refs: SpecRef[];
}

export interface Walkthrough {
  summary: string;
  steps: WalkthroughStep[];
  familiarity: number;
  depth: 'quick' | 'thorough';
  head_sha: string;
  generated_at: string;
}

export interface Capabilities {
  walkthrough: boolean;
  annotations: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface GenerateProgress {
  phase: 'starting' | 'cloning' | 'context' | 'annotating';
  batch?: number;
  total_batches?: number;
  detail?: string;
}
