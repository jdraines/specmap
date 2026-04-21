import { useMemo } from 'react';
import { tokenize, markEdits } from 'react-diff-view';
import type { HunkData } from 'react-diff-view';
import { refractor } from '../utils/refractorInstance';
import { detectLanguage } from '../utils/languageDetection';

export function useSyntaxTokens(
  hunks: HunkData[],
  filename: string,
  oldSource: string | null,
) {
  return useMemo(() => {
    const language = detectLanguage(filename);
    if (!language || hunks.length === 0) return undefined;

    try {
      return tokenize(hunks, {
        highlight: true,
        refractor,
        language,
        oldSource: oldSource ?? undefined,
        enhancers: [markEdits(hunks, { type: 'block' })],
      });
    } catch {
      return undefined;
    }
  }, [hunks, filename, oldSource]);
}
