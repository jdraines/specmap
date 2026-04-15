import { useState } from 'react';
import { useReviewStore } from '../../stores/reviewStore';
import { Spinner } from '../ui/Spinner';
import { useElapsedTime } from '../../hooks/useElapsedTime';

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
    text = `Completed ${progress.batch}/${progress.total_batches} batches...`;
  } else if (progress.phase === 'cloning') {
    text = 'Cloning repository...';
  } else if (progress.phase === 'context') {
    text = 'Analyzing PR context...';
  } else if (progress.phase === 'starting') {
    text = 'Starting annotation generation...';
  }

  return (
    <span className="text-xs text-[var(--text-secondary)]">
      <Spinner /> {text}
    </span>
  );
}

export function GenerateAnnotationsBanner({
  fullName,
  prNumber,
  hasAnnotations,
}: GenerateAnnotationsBannerProps) {
  const { generating, generateError, canGenerate, generateAnnotations, clearCache, clearingCache, specmapFile } =
    useReviewStore();
  const elapsed = useElapsedTime(generating);
  const [mode, setMode] = useState<'lite' | 'full'>('full');
  const [timeout, setTimeout_] = useState(300);
  const [timeoutInput, setTimeoutInput] = useState('300');
  const [concurrency, setConcurrency] = useState(4);
  const [concurrencyInput, setConcurrencyInput] = useState('4');

  if (!canGenerate) return null;

  const isPartial = specmapFile?.partial === true;

  // Existing annotations: show small regenerate link + clear cache button
  if (hasAnnotations) {
    return (
      <div className="font-sans flex items-center gap-2 mb-4 px-1 flex-wrap">
        <button
          onClick={() => generateAnnotations(fullName, prNumber, mode, true, timeout, false, concurrency)}
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
        {isPartial && !generating && (
          <>
            <span className="text-xs text-[var(--text-muted)]">·</span>
            <button
              onClick={() => generateAnnotations(fullName, prNumber, mode, false, timeout, true, concurrency)}
              disabled={generating || clearingCache}
              className="text-xs text-[var(--accent-text)] bg-transparent border-0 cursor-pointer underline hover:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Resume annotation generation ({specmapFile.completed_batches}/{specmapFile.total_batches} batches done)
            </button>
          </>
        )}
        <span className="text-xs text-[var(--text-muted)]">·</span>
        <button
          onClick={() => clearCache(fullName, prNumber)}
          disabled={generating || clearingCache}
          className="text-xs text-[var(--text-muted)] bg-transparent border-0 cursor-pointer underline hover:text-[var(--error-text)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {clearingCache ? 'Clearing...' : 'Clear cache'}
        </button>
        {generating && <><ProgressDisplay /> <span className="text-xs text-[var(--text-muted)]">{elapsed}</span></>}
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
          <span className="text-xs font-semibold text-[var(--text-secondary)] mr-1">mode:</span>
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
          <span className="text-xs font-semibold text-[var(--text-secondary)] mr-1">timeout:</span>
          <input
            type="number"
            min={30}
            max={1800}
            value={timeoutInput}
            onChange={(e) => setTimeoutInput(e.target.value)}
            onBlur={() => { const v = Math.max(30, Math.min(1800, Number(timeoutInput) || 300)); setTimeout_(v); setTimeoutInput(String(v)); }}
            className="w-16 px-1.5 py-1 text-xs border border-[var(--border)] bg-[var(--surface-1)] text-[var(--text-secondary)]"
          />
          <span className="text-xs text-[var(--text-muted)]">s</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs font-semibold text-[var(--text-secondary)] mr-1">concurrency:</span>
          <input
            type="number"
            min={1}
            max={8}
            value={concurrencyInput}
            onChange={(e) => setConcurrencyInput(e.target.value)}
            onBlur={() => { const v = Math.max(1, Math.min(8, Number(concurrencyInput) || 4)); setConcurrency(v); setConcurrencyInput(String(v)); }}
            className="w-12 px-1.5 py-1 text-xs border border-[var(--border)] bg-[var(--surface-1)] text-[var(--text-secondary)]"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => generateAnnotations(fullName, prNumber, mode, false, timeout, false, concurrency)}
          disabled={generating}
          className="px-3 py-1.5 text-xs bg-[var(--accent)] text-white border-0 cursor-pointer hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? 'Generating...' : 'Generate Annotations'}
        </button>
        {generating && <><ProgressDisplay /> <span className="text-xs text-[var(--text-muted)]">{elapsed}</span></>}
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
