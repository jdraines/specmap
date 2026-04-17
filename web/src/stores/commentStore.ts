import { create } from 'zustand';
import type { CommentThread, CommentsResponse, PostCommentRequest } from '../api/types';
import { comments } from '../api/endpoints';

interface CommentState {
  threads: CommentThread[];
  generalComments: CommentThread[];
  threadsByFile: Map<string, CommentThread[]>;
  loading: boolean;
  error: string | null;

  pollTimer: ReturnType<typeof setInterval> | null;

  drafts: Map<string, string>;

  conflicts: Map<string, { stale: CommentThread; fresh: CommentThread }>;

  submitting: boolean;

  fetchComments(fullName: string, number: number): Promise<void>;
  startPolling(fullName: string, number: number): void;
  stopPolling(): void;
  postComment(fullName: string, number: number, req: PostCommentRequest): Promise<boolean>;
  setDraft(key: string, text: string): void;
  clearConflict(threadId: string): void;
}

function buildThreadsByFile(threads: CommentThread[]): Map<string, CommentThread[]> {
  const byFile = new Map<string, CommentThread[]>();
  for (const t of threads) {
    if (!t.path) continue;
    const existing = byFile.get(t.path) ?? [];
    existing.push(t);
    byFile.set(t.path, existing);
  }
  return byFile;
}

function threadsFingerprint(threads: CommentThread[], general: CommentThread[]): string {
  const parts: string[] = [];
  for (const t of threads) {
    parts.push(`${t.thread_id}:${t.comment_count}:${t.latest_updated_at}`);
  }
  parts.push('|');
  for (const t of general) {
    parts.push(`${t.thread_id}:${t.comment_count}:${t.latest_updated_at}`);
  }
  return parts.join(',');
}

function applyResponse(data: CommentsResponse, get: () => CommentState): Partial<CommentState> | null {
  const state = get();
  const oldFp = threadsFingerprint(state.threads, state.generalComments);
  const newFp = threadsFingerprint(data.threads, data.general_comments);
  if (oldFp === newFp) return null;
  return {
    threads: data.threads,
    generalComments: data.general_comments,
    threadsByFile: buildThreadsByFile(data.threads),
    loading: false,
    error: null,
  };
}

export const useCommentStore = create<CommentState>((set, get) => ({
  threads: [],
  generalComments: [],
  threadsByFile: new Map(),
  loading: false,
  error: null,
  pollTimer: null,
  drafts: new Map(),
  conflicts: new Map(),
  submitting: false,

  fetchComments: async (fullName, number) => {
    set({ loading: true, error: null });
    try {
      const data = await comments.list(fullName, number);
      const update = applyResponse(data, get);
      if (update) {
        set(update);
      } else {
        set({ loading: false });
      }
    } catch (err) {
      set({ error: String(err), loading: false });
    }
  },

  startPolling: (fullName, number) => {
    const state = get();
    if (state.pollTimer) clearInterval(state.pollTimer);
    const timer = setInterval(() => {
      get().fetchComments(fullName, number);
    }, 60_000);
    set({ pollTimer: timer });
  },

  stopPolling: () => {
    const { pollTimer } = get();
    if (pollTimer) {
      clearInterval(pollTimer);
      set({ pollTimer: null });
    }
  },

  postComment: async (fullName, number, req) => {
    set({ submitting: true });

    // For replies, do conflict detection
    if (req.thread_id) {
      try {
        const freshData = await comments.list(fullName, number);
        const allThreads = [...freshData.threads, ...freshData.general_comments];
        const freshThread = allThreads.find((t) => t.thread_id === req.thread_id);
        const cachedThreads = [...get().threads, ...get().generalComments];
        const staleThread = cachedThreads.find((t) => t.thread_id === req.thread_id);

        if (freshThread && staleThread) {
          if (
            freshThread.comment_count !== staleThread.comment_count ||
            freshThread.latest_updated_at !== staleThread.latest_updated_at
          ) {
            // Conflict detected
            const conflicts = new Map(get().conflicts);
            conflicts.set(req.thread_id, { stale: staleThread, fresh: freshThread });
            const update = applyResponse(freshData, get);
            set({
              ...(update ?? {}),
              conflicts,
              submitting: false,
            });
            return false;
          }
        }
        // Also update state with fresh data
        const update = applyResponse(freshData, get);
        if (update) set(update);
      } catch {
        // If conflict check fails, proceed anyway
      }
    }

    try {
      await comments.post(fullName, number, req);
      // Refresh after posting
      const freshData = await comments.list(fullName, number);
      set({
        threads: freshData.threads,
        generalComments: freshData.general_comments,
        threadsByFile: buildThreadsByFile(freshData.threads),
        submitting: false,
      });
      // Clear draft
      const draftKey = req.thread_id ?? `new:${req.path ?? ''}:${req.line ?? ''}`;
      const drafts = new Map(get().drafts);
      drafts.delete(draftKey);
      set({ drafts });
      return true;
    } catch (err) {
      set({ error: String(err), submitting: false });
      return false;
    }
  },

  setDraft: (key, text) => {
    const drafts = new Map(get().drafts);
    if (text) {
      drafts.set(key, text);
    } else {
      drafts.delete(key);
    }
    set({ drafts });
  },

  clearConflict: (threadId) => {
    const conflicts = new Map(get().conflicts);
    conflicts.delete(threadId);
    set({ conflicts });
  },
}));
