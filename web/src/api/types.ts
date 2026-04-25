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
  token_hint?: string;
  current_repo?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface WalkthroughStep {
  step_number: number;
  title: string;
  narrative: string;
  file: string;
  start_line: number | null;
  end_line: number | null;
  refs: SpecRef[];
  chat?: ChatMessage[];
}

export interface Walkthrough {
  summary: string;
  steps: WalkthroughStep[];
  familiarity: number;
  depth: 'quick' | 'thorough';
  head_sha: string;
  generated_at: string;
}

export interface CodeReviewIssue {
  issue_number: number;
  severity: string;
  title: string;
  description: string;
  file: string;
  start_line: number | null;
  end_line: number | null;
  suggested_fix: string;
  category: string;
  chat?: ChatMessage[];
}

export interface CodeReview {
  summary: string;
  issues: CodeReviewIssue[];
  head_sha: string;
  generated_at: string;
}

export interface Capabilities {
  walkthrough: boolean;
  annotations: boolean;
  code_review: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface CommentReaction {
  emoji: string;
  count: number;
}

export interface Comment {
  id: string;
  author_login: string;
  author_avatar: string;
  body: string;
  created_at: string;
  updated_at: string;
  reactions: CommentReaction[];
}

export interface CommentThread {
  thread_id: string;
  path: string | null;
  line: number | null;
  side: 'LEFT' | 'RIGHT' | null;
  is_resolved: boolean;
  is_outdated: boolean;
  comments: Comment[];
  comment_count: number;
  latest_updated_at: string;
}

export interface CommentsResponse {
  threads: CommentThread[];
  general_comments: CommentThread[];
}

export interface PostCommentRequest {
  body: string;
  thread_id?: string;
  path?: string;
  line?: number;
  side?: string;
}

export interface GenerateProgress {
  phase: 'starting' | 'cloning' | 'context' | 'annotating';
  batch?: number;
  total_batches?: number;
  detail?: string;
}
