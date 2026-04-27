import { create } from 'zustand';
import type { ChatMessage, CodeReview } from '../api/types';
import { codeReview as codeReviewApi, capabilities } from '../api/endpoints';

interface ToolCallInfo {
  tool: string;
  args: unknown;
  result?: string;
}

interface CodeReviewState {
  review: CodeReview | null;
  active: boolean;
  currentIssue: number; // 0-indexed
  loading: boolean;
  error: string | null;
  maxIssues: number;
  timeout: number; // seconds
  customPrompt: string;
  contextLines: number;
  chunkThreshold: number;
  available: boolean;

  // Chat state
  chatExpanded: Record<number, boolean>;
  chatStreaming: number | null;
  chatStreamContent: string;
  chatToolCalls: ToolCallInfo[];
  chatError: string | null;

  setMaxIssues: (n: number) => void;
  setTimeout: (t: number) => void;
  setCustomPrompt: (p: string) => void;
  setContextLines: (n: number) => void;
  setChunkThreshold: (n: number) => void;
  generate: (fullName: string, number: number, force?: boolean) => Promise<void>;
  cancelGenerate: () => void;
  start: () => void;
  exit: () => void;
  nextIssue: () => void;
  prevIssue: () => void;
  goToIssue: (issue: number) => void;
  checkAvailable: () => Promise<void>;
  reset: () => void;
  toggleChat: (issueNumber: number) => void;
  sendMessage: (fullName: string, prNumber: number, issueNumber: number, message: string) => Promise<void>;
}

function loadStorage<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v !== null ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
}

export const useCodeReviewStore = create<CodeReviewState>((set, get) => ({
  review: null,
  active: false,
  currentIssue: 0,
  loading: false,
  error: null,
  maxIssues: loadStorage('specmap-cr-max-issues', 20),
  timeout: loadStorage('specmap-cr-timeout', 300),
  customPrompt: '',
  contextLines: loadStorage('specmap-cr-context-lines', 10),
  chunkThreshold: loadStorage('specmap-cr-chunk-threshold', 500),
  available: false,

  chatExpanded: {},
  chatStreaming: null,
  chatStreamContent: '',
  chatToolCalls: [],
  chatError: null,

  setMaxIssues: (n) => {
    localStorage.setItem('specmap-cr-max-issues', JSON.stringify(n));
    set({ maxIssues: n });
  },

  setTimeout: (t) => {
    localStorage.setItem('specmap-cr-timeout', JSON.stringify(t));
    set({ timeout: t });
  },

  setCustomPrompt: (p) => set({ customPrompt: p }),

  setContextLines: (n) => {
    localStorage.setItem('specmap-cr-context-lines', JSON.stringify(n));
    set({ contextLines: n });
  },

  setChunkThreshold: (n) => {
    localStorage.setItem('specmap-cr-chunk-threshold', JSON.stringify(n));
    set({ chunkThreshold: n });
  },

  generate: async (fullName, number, force) => {
    const { maxIssues, timeout, customPrompt, contextLines, chunkThreshold } = get();

    const controller = new AbortController();
    (get() as any)._generateController = controller;
    set({ loading: true, error: null });
    try {
      const cr = await codeReviewApi.generate(fullName, number, maxIssues, timeout, contextLines, chunkThreshold, customPrompt || undefined, force, controller.signal);
      set({ review: cr, loading: false });
    } catch (e) {
      if (controller.signal.aborted) {
        set({ loading: false, error: null });
        return;
      }
      let msg: string;
      if (e instanceof DOMException && e.name === 'AbortError') {
        msg = 'Code review timed out — the PR may be too large.';
      } else {
        msg = e instanceof Error ? e.message : 'Failed to generate code review';
      }
      set({ error: msg, loading: false });
    } finally {
      (get() as any)._generateController = null;
    }
  },

  cancelGenerate: () => {
    const controller = (get() as any)._generateController as AbortController | null;
    if (controller) {
      controller.abort();
    }
    set({ loading: false, error: null });
  },

  start: () => set({ active: true, currentIssue: 0 }),

  exit: () => set({ active: false }),

  nextIssue: () => {
    const { currentIssue, review } = get();
    if (review && currentIssue < review.issues.length - 1) {
      set({ currentIssue: currentIssue + 1 });
    }
  },

  prevIssue: () => {
    const { currentIssue } = get();
    if (currentIssue > 0) {
      set({ currentIssue: currentIssue - 1 });
    }
  },

  goToIssue: (issue) => {
    const { review } = get();
    if (review && issue >= 0 && issue < review.issues.length) {
      set({ currentIssue: issue });
    }
  },

  checkAvailable: async () => {
    try {
      const caps = await capabilities.get();
      set({ available: caps.code_review });
    } catch {
      set({ available: false });
    }
  },

  reset: () =>
    set({
      review: null,
      active: false,
      currentIssue: 0,
      loading: false,
      error: null,
      chatExpanded: {},
      chatStreaming: null,
      chatStreamContent: '',
      chatToolCalls: [],
      chatError: null,
    }),

  toggleChat: (issueNumber) => {
    const { chatExpanded } = get();
    set({ chatExpanded: { ...chatExpanded, [issueNumber]: !chatExpanded[issueNumber] } });
  },

  sendMessage: async (fullName, prNumber, issueNumber, message) => {
    const { review, chatExpanded } = get();
    if (!review) return;

    const issueIdx = review.issues.findIndex((iss) => iss.issue_number === issueNumber);
    if (issueIdx === -1) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    const updatedIssues = [...review.issues];
    const updatedIssue = { ...updatedIssues[issueIdx] };
    updatedIssue.chat = [...(updatedIssue.chat ?? []), userMsg];
    updatedIssues[issueIdx] = updatedIssue;

    set({
      review: { ...review, issues: updatedIssues },
      chatExpanded: { ...chatExpanded, [issueNumber]: true },
      chatStreaming: issueNumber,
      chatStreamContent: '',
      chatToolCalls: [],
      chatError: null,
    });

    try {
      await codeReviewApi.chat(fullName, prNumber, issueNumber, message, {
        onDelta: (content) => {
          set((state) => ({ chatStreamContent: state.chatStreamContent + content }));
        },
        onToolCall: (tool, args) => {
          set((state) => ({
            chatToolCalls: [...state.chatToolCalls, { tool, args }],
          }));
        },
        onToolResult: (tool, summary) => {
          set((state) => ({
            chatToolCalls: state.chatToolCalls.map((tc) =>
              tc.tool === tool && !tc.result ? { ...tc, result: summary } : tc,
            ),
          }));
        },
        onDone: (asstMsg) => {
          const current = get().review;
          if (!current) return;
          const issues = [...current.issues];
          const idx = issues.findIndex((iss) => iss.issue_number === issueNumber);
          if (idx === -1) return;
          const issue = { ...issues[idx] };
          issue.chat = [...(issue.chat ?? []), asstMsg];
          issues[idx] = issue;
          set({
            review: { ...current, issues },
            chatStreaming: null,
            chatStreamContent: '',
            chatToolCalls: [],
          });
        },
        onError: (msg) => {
          set({ chatStreaming: null, chatStreamContent: '', chatToolCalls: [], chatError: msg });
        },
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Chat failed';
      set({ chatStreaming: null, chatStreamContent: '', chatToolCalls: [], chatError: msg });
    }
  },
}));
