import { useState } from 'react';
import { useReviewStore } from '../../stores/reviewStore';
import { Spinner } from '../ui/Spinner';

interface GenerateAnnotationsBannerProps {
  owner: string;
  repo: string;
  prNumber: number;
  hasAnnotations: boolean;
}

const modeOptions = [
  { value: 'lite' as const, label: 'lite' },
  { value: 'full' as const, label: 'full (recommended)' },
] as const;

export function GenerateAnnotationsBanner({
  owner,
  repo,
  prNumber,
  hasAnnotations,
}: GenerateAnnotationsBannerProps) {
  const { generating, generateError, canGenerate, generateAnnotations } = useReviewStore();
  const [mode, setMode] = useState<'lite' | 'full'>('full');

  if (!canGenerate) return null;

  // Existing annotations: show small regenerate link
  if (hasAnnotations) {
    return (
      <div className="flex items-center gap-2 mb-4 px-1">
        <button
          onClick={() => generateAnnotations(owner, repo, prNumber, mode, true)}
          disabled={generating}
          className="text-xs text-[var(--text-muted)] bg-transparent border-0 cursor-pointer underline hover:text-[var(--text-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? 'Regenerating...' : 'Regenerate annotations'}
        </button>
        {generateError && (
          <span className="text-xs text-[var(--error-text)]">{generateError}</span>
        )}
      </div>
    );
  }

  // No annotations: show full banner
  return (
    <div className="border border-[var(--wt-border)] bg-gradient-to-r from-[var(--wt-gradient-from)] to-[var(--wt-gradient-to)] p-4 mb-4">
      <p className="text-sm text-[var(--text-secondary)] mb-3">
        This PR has no specmap annotations. Generate them server-side to enable spec-linked review.
      </p>

      <div className="flex flex-wrap items-center gap-4 mb-3">
        <div className="flex items-center gap-1">
          <span className="text-xs text-[var(--text-muted)] mr-1">mode:</span>
          {modeOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setMode(opt.value)}
              className={`px-2 py-1 text-xs border cursor-pointer ${
                mode === opt.value
                  ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                  : 'bg-[var(--surface-1)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--text-muted)]'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => generateAnnotations(owner, repo, prNumber, mode)}
          disabled={generating}
          className="px-3 py-1.5 text-xs bg-[var(--accent)] text-white border-0 cursor-pointer hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? 'Generating...' : 'Generate Annotations'}
        </button>
        {generating && (
          <span className="text-xs text-[var(--text-muted)]">
            <Spinner /> Generating annotations...
          </span>
        )}
      </div>

      {generateError && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-xs text-[var(--error-text)]">{generateError}</p>
          <button
            onClick={() => generateAnnotations(owner, repo, prNumber, mode)}
            className="text-xs text-[var(--accent-text)] bg-transparent border-0 cursor-pointer underline"
          >
            retry
          </button>
        </div>
      )}
    </div>
  );
}
