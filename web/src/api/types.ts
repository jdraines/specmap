export interface User {
  id: number;
  github_id: number;
  login: string;
  name: string;
  avatar_url: string;
  created_at: string;
  updated_at: string;
}

export interface Repository {
  id: number;
  github_id: number;
  owner: string;
  name: string;
  full_name: string;
  private: boolean;
  created_at: string;
  updated_at: string;
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
}

export interface SpecContent {
  path: string;
  content: string;
}
