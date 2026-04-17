import { create } from 'zustand';
import type { SpecRef, SpecContent, Annotation, WalkthroughStep } from '../api/types';
import { specs } from '../api/endpoints';

interface SpecPanelState {
  // Modal/drawer state
  modalRef: SpecRef | null;
  isModalOpen: boolean;

  // Context for fetching spec content
  fullName: string;
  prNumber: number;

  // Cache
  cachedContent: Map<string, SpecContent>;
  preloading: boolean;

  // Actions
  openModal: (ref: SpecRef) => void;
  closeModal: () => void;
  setContext: (fullName: string, prNumber: number) => void;
  cacheContent: (path: string, content: SpecContent) => void;
  preloadSpecs: (annotations: Annotation[], walkthroughSteps?: WalkthroughStep[]) => void;
}

export const useSpecPanelStore = create<SpecPanelState>((set, get) => ({
  modalRef: null,
  isModalOpen: false,
  fullName: '',
  prNumber: 0,
  cachedContent: new Map(),
  preloading: false,
  openModal: (ref) => set({ isModalOpen: true, modalRef: ref }),
  closeModal: () => set({ isModalOpen: false, modalRef: null }),
  setContext: (fullName, prNumber) => set({ fullName, prNumber }),
  cacheContent: (path, content) =>
    set((state) => {
      const next = new Map(state.cachedContent);
      next.set(path, content);
      return { cachedContent: next };
    }),
  preloadSpecs: (annotations, walkthroughSteps) => {
    const { fullName, prNumber, cachedContent } = get();
    if (!fullName || !prNumber) return;

    // Collect unique spec file paths from all refs
    const paths = new Set<string>();
    for (const ann of annotations) {
      for (const ref of ann.refs) {
        paths.add(ref.spec_file);
      }
    }
    if (walkthroughSteps) {
      for (const step of walkthroughSteps) {
        for (const ref of step.refs) {
          paths.add(ref.spec_file);
        }
      }
    }

    // Filter out already-cached paths
    const toFetch = [...paths].filter((p) => !cachedContent.has(p));
    if (toFetch.length === 0) return;

    set({ preloading: true });
    Promise.all(
      toFetch.map((path) =>
        specs.content(fullName, prNumber, path).then((content) => {
          get().cacheContent(path, content);
        }).catch(() => {
          // Silently skip failed fetches; will retry on click
        }),
      ),
    ).finally(() => set({ preloading: false }));
  },
}));
