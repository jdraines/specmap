import { create } from 'zustand';
import type { ChatMessage, Walkthrough } from '../api/types';
import { walkthrough as walkthroughApi, capabilities } from '../api/endpoints';

function walkthroughKey(f: number, d: string): string {
  return `f${f}.${d}`;
}

interface ToolCallInfo {
  tool: string;
  args: unknown;
  result?: string;
}

interface WalkthroughState {
  walkthrough: Walkthrough | null;
  cache: Record<string, Walkthrough>;
  active: boolean;
  currentStep: number; // 0-indexed
  loading: boolean;
  error: string | null;
  familiarity: number; // 1-3
  depth: 'quick' | 'thorough';
  available: boolean; // from capabilities

  // Chat state
  chatExpanded: Record<number, boolean>; // step_number → expanded
  chatStreaming: number | null; // step currently streaming, or null
  chatStreamContent: string; // accumulating response text
  chatToolCalls: ToolCallInfo[]; // tool calls in progress
  chatError: string | null;

  setFamiliarity: (f: number) => void;
  setDepth: (d: 'quick' | 'thorough') => void;
  generate: (fullName: string, number: number) => Promise<void>;
  cancelGenerate: () => void;
  start: () => void;
  exit: () => void;
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (step: number) => void;
  checkAvailable: () => Promise<void>;
  reset: () => void;
  toggleChat: (stepNumber: number) => void;
  sendMessage: (fullName: string, prNumber: number, stepNumber: number, message: string) => Promise<void>;
}

function loadStorage<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v !== null ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
}

export const useWalkthroughStore = create<WalkthroughState>((set, get) => ({
  walkthrough: null,
  cache: {},
  active: false,
  currentStep: 0,
  loading: false,
  error: null,
  familiarity: loadStorage('specmap-wt-familiarity', 2),
  depth: loadStorage('specmap-wt-depth', 'quick'),
  available: false,

  // Chat state
  chatExpanded: {},
  chatStreaming: null,
  chatStreamContent: '',
  chatToolCalls: [],
  chatError: null,

  setFamiliarity: (f) => {
    localStorage.setItem('specmap-wt-familiarity', JSON.stringify(f));
    const { cache, depth } = get();
    const cached = cache[walkthroughKey(f, depth)];
    set({ familiarity: f, ...(cached ? { walkthrough: cached, currentStep: 0 } : {}) });
  },

  setDepth: (d) => {
    localStorage.setItem('specmap-wt-depth', JSON.stringify(d));
    const { cache, familiarity } = get();
    const cached = cache[walkthroughKey(familiarity, d)];
    set({ depth: d, ...(cached ? { walkthrough: cached, currentStep: 0 } : {}) });
  },

  generate: async (fullName, number) => {
    const { familiarity, depth, cache } = get();
    const key = walkthroughKey(familiarity, depth);

    // Return cached variant if head_sha matches (instant switch)
    const cached = cache[key];
    if (cached) {
      // We still call the API to let the server check staleness, but
      // the server will return instantly if head_sha matches.
    }

    const controller = new AbortController();
    (get() as any)._generateController = controller;
    set({ loading: true, error: null });
    try {
      const wt = await walkthroughApi.generate(fullName, number, familiarity, depth, controller.signal);
      set((state) => ({
        walkthrough: wt,
        loading: false,
        cache: { ...state.cache, [key]: wt },
      }));
    } catch (e) {
      if (controller.signal.aborted) {
        set({ loading: false, error: null });
        return;
      }
      let msg: string;
      if (e instanceof DOMException && e.name === 'AbortError') {
        msg = "Generation was cancelled or the connection was lost.";
      } else {
        msg = e instanceof Error ? e.message : 'Failed to generate walkthrough';
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

  start: () => set({ active: true, currentStep: 0 }),

  exit: () => set({ active: false }),

  nextStep: () => {
    const { currentStep, walkthrough } = get();
    if (walkthrough && currentStep < walkthrough.steps.length - 1) {
      set({ currentStep: currentStep + 1 });
    }
  },

  prevStep: () => {
    const { currentStep } = get();
    if (currentStep > 0) {
      set({ currentStep: currentStep - 1 });
    }
  },

  goToStep: (step) => {
    const { walkthrough } = get();
    if (walkthrough && step >= 0 && step < walkthrough.steps.length) {
      set({ currentStep: step });
    }
  },

  checkAvailable: async () => {
    try {
      const caps = await capabilities.get();
      set({ available: caps.walkthrough });
    } catch {
      set({ available: false });
    }
  },

  reset: () =>
    set({
      walkthrough: null,
      cache: {},
      active: false,
      currentStep: 0,
      loading: false,
      error: null,
      chatExpanded: {},
      chatStreaming: null,
      chatStreamContent: '',
      chatToolCalls: [],
      chatError: null,
    }),

  toggleChat: (stepNumber) => {
    const { chatExpanded } = get();
    set({ chatExpanded: { ...chatExpanded, [stepNumber]: !chatExpanded[stepNumber] } });
  },

  sendMessage: async (fullName, prNumber, stepNumber, message) => {
    const { walkthrough, familiarity, depth, chatExpanded } = get();
    if (!walkthrough) return;

    // Find the step and add user message optimistically
    const stepIdx = walkthrough.steps.findIndex((s) => s.step_number === stepNumber);
    if (stepIdx === -1) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    const updatedSteps = [...walkthrough.steps];
    const updatedStep = { ...updatedSteps[stepIdx] };
    updatedStep.chat = [...(updatedStep.chat ?? []), userMsg];
    updatedSteps[stepIdx] = updatedStep;

    set({
      walkthrough: { ...walkthrough, steps: updatedSteps },
      chatExpanded: { ...chatExpanded, [stepNumber]: true },
      chatStreaming: stepNumber,
      chatStreamContent: '',
      chatToolCalls: [],
      chatError: null,
    });

    try {
      await walkthroughApi.chat(fullName, prNumber, stepNumber, message, familiarity, depth, {
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
          const current = get().walkthrough;
          if (!current) return;
          const steps = [...current.steps];
          const idx = steps.findIndex((s) => s.step_number === stepNumber);
          if (idx === -1) return;
          const step = { ...steps[idx] };
          step.chat = [...(step.chat ?? []), asstMsg];
          steps[idx] = step;
          set({
            walkthrough: { ...current, steps },
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
