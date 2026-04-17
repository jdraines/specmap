import { create } from 'zustand';

type AnnotationMode = 'inline' | 'side' | 'auto';
type ResolvedMode = 'inline' | 'side';

interface LayoutState {
  annotationMode: AnnotationMode;
  resolvedMode: ResolvedMode;
  fileTreeOpen: boolean;
  setAnnotationMode: (mode: AnnotationMode) => void;
  updateResolved: (viewportWidth: number) => void;
  toggleFileTree: () => void;
}

const BREAKPOINT = 1400;

function resolveMode(mode: AnnotationMode, width: number): ResolvedMode {
  if (mode === 'auto') return width >= BREAKPOINT ? 'side' : 'inline';
  return mode;
}

const stored = (localStorage.getItem('specmap-layout') as AnnotationMode | null) ?? 'auto';
const storedFileTree = localStorage.getItem('specmap-filetree') !== 'false';

export const useLayoutStore = create<LayoutState>((set, get) => ({
  annotationMode: stored,
  resolvedMode: resolveMode(stored, typeof window !== 'undefined' ? window.innerWidth : 0),
  fileTreeOpen: storedFileTree,
  setAnnotationMode: (mode) => {
    localStorage.setItem('specmap-layout', mode);
    const resolved = resolveMode(mode, window.innerWidth);
    set({ annotationMode: mode, resolvedMode: resolved });
  },
  updateResolved: (viewportWidth) => {
    const { annotationMode } = get();
    const resolved = resolveMode(annotationMode, viewportWidth);
    set({ resolvedMode: resolved });
  },
  toggleFileTree: () => {
    const next = !get().fileTreeOpen;
    localStorage.setItem('specmap-filetree', String(next));
    set({ fileTreeOpen: next });
  },
}));

// Auto-update on viewport resize
if (typeof window !== 'undefined') {
  window.addEventListener('resize', () => {
    useLayoutStore.getState().updateResolved(window.innerWidth);
  });
}
