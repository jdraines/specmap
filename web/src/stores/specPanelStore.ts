import { create } from 'zustand';
import type { SpecRef, SpecContent } from '../api/types';

interface SpecPanelState {
  // Modal/drawer state
  modalRef: SpecRef | null;
  isModalOpen: boolean;

  // Context for fetching spec content
  owner: string;
  repo: string;
  prNumber: number;

  // Cache
  cachedContent: Map<string, SpecContent>;

  // Actions
  openModal: (ref: SpecRef) => void;
  closeModal: () => void;
  setContext: (owner: string, repo: string, prNumber: number) => void;
  cacheContent: (path: string, content: SpecContent) => void;
}

export const useSpecPanelStore = create<SpecPanelState>((set) => ({
  modalRef: null,
  isModalOpen: false,
  owner: '',
  repo: '',
  prNumber: 0,
  cachedContent: new Map(),
  openModal: (ref) => set({ isModalOpen: true, modalRef: ref }),
  closeModal: () => set({ isModalOpen: false, modalRef: null }),
  setContext: (owner, repo, prNumber) => set({ owner, repo, prNumber }),
  cacheContent: (path, content) =>
    set((state) => {
      const next = new Map(state.cachedContent);
      next.set(path, content);
      return { cachedContent: next };
    }),
}));
