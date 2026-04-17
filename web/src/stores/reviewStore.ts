import { create } from 'zustand';
import type { PullRequest, PullFile, SpecmapFile, Annotation, GenerateProgress } from '../api/types';
import { pulls, capabilities } from '../api/endpoints';
import { useWalkthroughStore } from './walkthroughStore';

interface ReviewState {
  pr: PullRequest | null;
  files: PullFile[];
  specmapFile: SpecmapFile | null;
  annotationsByFile: Map<string, Annotation[]>;
  loading: boolean;
  error: string | null;
  generating: boolean;
  generateError: string | null;
  generateProgress: GenerateProgress | null;
  canGenerate: boolean;
  clearingCache: boolean;
  fetchReview: (fullName: string, number: number) => Promise<void>;
  generateAnnotations: (
    fullName: string,
    number: number,
    mode?: 'lite' | 'full',
    force?: boolean,
    timeout?: number,
    resume?: boolean,
    concurrency?: number,
  ) => Promise<void>;
  clearCache: (fullName: string, number: number) => Promise<void>;
  checkCanGenerate: () => Promise<void>;
}

function buildAnnotationsByFile(annotations: Annotation[]): Map<string, Annotation[]> {
  const byFile = new Map<string, Annotation[]>();
  for (const ann of annotations) {
    const existing = byFile.get(ann.file) ?? [];
    existing.push(ann);
    byFile.set(ann.file, existing);
  }
  return byFile;
}

export const useReviewStore = create<ReviewState>((set) => ({
  pr: null,
  files: [],
  specmapFile: null,
  annotationsByFile: new Map(),
  loading: false,
  error: null,
  generating: false,
  generateError: null,
  generateProgress: null,
  canGenerate: false,
  clearingCache: false,
  fetchReview: async (fullName, number) => {
    set({ loading: true, error: null });
    try {
      const [pr, files, specmap] = await Promise.all([
        pulls.get(fullName, number),
        pulls.files(fullName, number),
        pulls.annotations(fullName, number),
      ]);

      set({
        pr,
        files,
        specmapFile: specmap,
        annotationsByFile: buildAnnotationsByFile(specmap.annotations ?? []),
        loading: false,
      });
    } catch (err) {
      set({ error: String(err), loading: false });
    }
  },
  generateAnnotations: async (fullName, number, mode = 'full', force = false, timeout?: number, resume = false, concurrency = 4) => {
    set({ generating: true, generateError: null, generateProgress: null });
    try {
      const specmap = await pulls.generateAnnotations(
        fullName, number, mode, force, timeout,
        (progress) => set({ generateProgress: progress }),
        resume, concurrency,
      );
      const partialMsg = specmap.partial
        ? `Partial results: ${specmap.completed_batches}/${specmap.total_batches} batches completed. Increase timeout or resume to continue.`
        : null;
      set({
        specmapFile: specmap,
        annotationsByFile: buildAnnotationsByFile(specmap.annotations ?? []),
        generating: false,
        generateProgress: null,
        generateError: partialMsg,
      });
    } catch (e) {
      let msg: string;
      if (e instanceof DOMException && e.name === 'AbortError') {
        msg = "Generation timed out — the PR may be too large. Try 'lite' mode or increase timeout.";
      } else {
        msg = e instanceof Error ? e.message : 'Failed to generate annotations';
      }
      set({ generateError: msg, generating: false, generateProgress: null });
    }
  },
  clearCache: async (fullName, number) => {
    set({ clearingCache: true });
    try {
      await pulls.clearCache(fullName, number);
      set({
        specmapFile: null,
        annotationsByFile: new Map(),
        clearingCache: false,
      });
      useWalkthroughStore.getState().reset();
    } catch {
      set({ clearingCache: false });
    }
  },
  checkCanGenerate: async () => {
    try {
      const caps = await capabilities.get();
      set({ canGenerate: caps.annotations });
    } catch {
      set({ canGenerate: false });
    }
  },
}));
