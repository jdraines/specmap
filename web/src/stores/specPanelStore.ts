import { create } from 'zustand';
import type { SpecRef, SpecContent } from '../api/types';

interface SpecPanelState {
  isOpen: boolean;
  activeRef: SpecRef | null;
  owner: string;
  repo: string;
  prNumber: number;
  cachedContent: Map<string, SpecContent>;
  open: (ref: SpecRef) => void;
  close: () => void;
  setContext: (owner: string, repo: string, prNumber: number) => void;
  cacheContent: (path: string, content: SpecContent) => void;
}

export const useSpecPanelStore = create<SpecPanelState>((set) => ({
  isOpen: false,
  activeRef: null,
  owner: '',
  repo: '',
  prNumber: 0,
  cachedContent: new Map(),
  open: (ref) => set({ isOpen: true, activeRef: ref }),
  close: () => set({ isOpen: false, activeRef: null }),
  setContext: (owner, repo, prNumber) => set({ owner, repo, prNumber }),
  cacheContent: (path, content) =>
    set((state) => {
      const next = new Map(state.cachedContent);
      next.set(path, content);
      return { cachedContent: next };
    }),
}));
