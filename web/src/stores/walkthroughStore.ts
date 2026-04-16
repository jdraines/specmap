import { create } from 'zustand';
import type { Walkthrough } from '../api/types';
import { walkthrough as walkthroughApi, capabilities } from '../api/endpoints';

function walkthroughKey(f: number, d: string): string {
  return `f${f}.${d}`;
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
  timeout: number; // seconds
  available: boolean; // from capabilities

  setFamiliarity: (f: number) => void;
  setDepth: (d: 'quick' | 'thorough') => void;
  setTimeout: (t: number) => void;
  generate: (fullName: string, number: number) => Promise<void>;
  start: () => void;
  exit: () => void;
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (step: number) => void;
  checkAvailable: () => Promise<void>;
  reset: () => void;
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
  timeout: loadStorage('specmap-wt-timeout', 300),
  available: false,

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

  setTimeout: (t) => {
    localStorage.setItem('specmap-wt-timeout', JSON.stringify(t));
    set({ timeout: t });
  },

  generate: async (fullName, number) => {
    const { familiarity, depth, timeout, cache } = get();
    const key = walkthroughKey(familiarity, depth);

    // Return cached variant if head_sha matches (instant switch)
    const cached = cache[key];
    if (cached) {
      // We still call the API to let the server check staleness, but
      // the server will return instantly if head_sha matches.
    }

    set({ loading: true, error: null });
    try {
      const wt = await walkthroughApi.generate(fullName, number, familiarity, depth, timeout);
      set((state) => ({
        walkthrough: wt,
        loading: false,
        cache: { ...state.cache, [key]: wt },
      }));
    } catch (e) {
      let msg: string;
      if (e instanceof DOMException && e.name === 'AbortError') {
        msg = "Generation timed out — the PR may be too large. Try 'quick' depth or increase timeout.";
      } else {
        msg = e instanceof Error ? e.message : 'Failed to generate walkthrough';
      }
      set({ error: msg, loading: false });
    }
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
    }),
}));
