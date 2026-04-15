import { useState } from 'react';
import { useReviewStore } from '../../stores/reviewStore';
import { Spinner } from '../ui/Spinner';

interface GenerateAnnotationsBannerProps {
  fullName: string;
  prNumber: number;
  hasAnnotations: boolean;
}

const modeOptions = [
  { value: 'lite' as const, label: 'lite' },
  { value: 'full' as const, label: 'full (recommended)' },
] as const;

function ProgressDisplay() {
  const progress = useReviewStore((s) => s.generateProgress);
  if (!progress) return null;

  let text = progress.detail ?? '';
  if (progress.phase === 'annotating' && progress.batch != null && progress.total_batches != null) {
    text = `Annotating batch ${progress.batch}/${progress.total_batches}...`;
  } else if (progress.phase === 'cloning') {
    text = 'Cloning repository...';
  } else if (progress.phase === 'context') {
    text = 'Analyzing PR context...';
  } else if (progress.phase === 'starting') {
    text = 'Starting annotation generation...';
  }

  return (
    <span className="text-xs text-white">
      <Spinner /> {text}
    </span>
  );
}

export function GenerateAnnotationsBanner({
  fullName,
  prNumber,
  hasAnnotations,
}: GenerateAnnotationsBannerProps) {
  const { generating, generateError, canGenerate, generateAnnotations, clearCache, clearingCache } =
    useReviewStore();
  const [mode, setMode] = useState<'lite' | 'full'>('full');
  const [timeout, setTimeout_] = useState(120);

  if (!canGenerate) return null;

  // Existing annotations: show small regenerate link + clear cache button
  if (hasAnnotations) {
    return (
      <div className="font-sans flex items-center gap-2 mb-4 px-1">
        <button
          onClick={() => generateAnnotations(fullName, prNumber, mode, true, timeout)}
          disabled={generating || clearingCache}
          className="text-xs text-[var(--text-muted)] bg-transparent border-0 cursor-pointer underline hover:text-[var(--text-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? (
            <>
              <Spinner /> Regenerating...
            </>
          ) : (
            'Regenerate annotations'
          )}
        </button>
        <span className="text-xs text-[var(--text-muted)]">·</span>
        <button
          onClick={() => clearCache(fullName, prNumber)}
          disabled={generating || clearingCache}
          className="text-xs text-[var(--text-muted)] bg-transparent border-0 cursor-pointer underline hover:text-[var(--error-text)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {clearingCache ? 'Clearing...' : 'Clear cache'}
        </button>
        {generating && <ProgressDisplay />}
        {generateError && (
          <span className="text-xs text-[var(--error-text)]">{generateError}</span>
        )}
      </div>
    );
  }

  // No annotations: show full banner
  return (
    <div className="font-sans border border-[var(--wt-border)] bg-gradient-to-r from-[var(--wt-gradient-from)] to-[var(--wt-gradient-to)] p-4 mb-4">
      <p className="text-sm text-[var(--text-secondary)] mb-3">
        This PR has no specmap annotations. Generate them server-side to enable spec-linked review.
      </p>

      <div className="flex flex-wrap items-center gap-4 mb-3">
        <div className="flex items-center gap-1">
          <span className="text-xs font-semibold text-white mr-1">mode:</span>
          {modeOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setMode(opt.value)}
              className={`px-2 py-1 text-xs font-medium border cursor-pointer ${
                mode === opt.value
                  ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                  : 'bg-[var(--surface-1)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--text-muted)]'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs font-semibold text-white mr-1">timeout:</span>
          <input
            type="number"
            min={30}
            max={600}
            value={timeout}
            onChange={(e) => setTimeout_(Math.max(30, Math.min(600, Number(e.target.value))))}
            className="w-16 px-1.5 py-1 text-xs border border-[var(--border)] bg-[var(--surface-1)] text-[var(--text-secondary)]"
          />
          <span className="text-xs text-[var(--text-muted)]">s</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => generateAnnotations(fullName, prNumber, mode, false, timeout)}
          disabled={generating}
          className="px-3 py-1.5 text-xs bg-[var(--accent)] text-white border-0 cursor-pointer hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? 'Generating...' : 'Generate Annotations'}
        </button>
        {generating && <ProgressDisplay />}
      </div>

      {generateError && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-xs text-[var(--error-text)]">{generateError}</p>
          <button
            onClick={() => generateAnnotations(fullName, prNumber, mode, false, timeout)}
            className="text-xs text-[var(--accent-text)] bg-transparent border-0 cursor-pointer underline"
          >
            retry
          </button>
        </div>
      )}
    </div>
  );
}
