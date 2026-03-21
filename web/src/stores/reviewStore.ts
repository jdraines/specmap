import { create } from 'zustand';
import type { PullRequest, PullFile, SpecmapFile, Annotation } from '../api/types';
import { pulls } from '../api/endpoints';

interface ReviewState {
  pr: PullRequest | null;
  files: PullFile[];
  specmapFile: SpecmapFile | null;
  annotationsByFile: Map<string, Annotation[]>;
  loading: boolean;
  error: string | null;
  fetchReview: (owner: string, repo: string, number: number) => Promise<void>;
}

export const useReviewStore = create<ReviewState>((set) => ({
  pr: null,
  files: [],
  specmapFile: null,
  annotationsByFile: new Map(),
  loading: false,
  error: null,
  fetchReview: async (owner, repo, number) => {
    set({ loading: true, error: null });
    try {
      const [pr, files, specmap] = await Promise.all([
        pulls.get(owner, repo, number),
        pulls.files(owner, repo, number),
        pulls.annotations(owner, repo, number),
      ]);

      const byFile = new Map<string, Annotation[]>();
      for (const ann of specmap.annotations ?? []) {
        const existing = byFile.get(ann.file) ?? [];
        existing.push(ann);
        byFile.set(ann.file, existing);
      }

      set({ pr, files, specmapFile: specmap, annotationsByFile: byFile, loading: false });
    } catch (err) {
      set({ error: String(err), loading: false });
    }
  },
}));
