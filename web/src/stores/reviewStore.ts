import { create } from 'zustand';
import type { PullRequest, PullFile, SpecmapFile, Annotation } from '../api/types';
import { pulls, capabilities } from '../api/endpoints';

interface ReviewState {
  pr: PullRequest | null;
  files: PullFile[];
  specmapFile: SpecmapFile | null;
  annotationsByFile: Map<string, Annotation[]>;
  loading: boolean;
  error: string | null;
  generating: boolean;
  generateError: string | null;
  canGenerate: boolean;
  fetchReview: (owner: string, repo: string, number: number) => Promise<void>;
  generateAnnotations: (
    owner: string,
    repo: string,
    number: number,
    mode?: 'lite' | 'full',
    force?: boolean,
  ) => Promise<void>;
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

export const useReviewStore = create<ReviewState>((set, _get) => ({
  pr: null,
  files: [],
  specmapFile: null,
  annotationsByFile: new Map(),
  loading: false,
  error: null,
  generating: false,
  generateError: null,
  canGenerate: false,
  fetchReview: async (owner, repo, number) => {
    set({ loading: true, error: null });
    try {
      const [pr, files, specmap] = await Promise.all([
        pulls.get(owner, repo, number),
        pulls.files(owner, repo, number),
        pulls.annotations(owner, repo, number),
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
  generateAnnotations: async (owner, repo, number, mode = 'full', force = false) => {
    set({ generating: true, generateError: null });
    try {
      const specmap = await pulls.generateAnnotations(owner, repo, number, mode, force);
      set({
        specmapFile: specmap,
        annotationsByFile: buildAnnotationsByFile(specmap.annotations ?? []),
        generating: false,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to generate annotations';
      set({ generateError: msg, generating: false });
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
