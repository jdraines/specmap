import { useState } from 'react';
import { useCodeReviewStore } from '../../stores/codeReviewStore';
import { Spinner } from '../ui/Spinner';
import { useElapsedTime } from '../../hooks/useElapsedTime';

interface CodeReviewBannerProps {
  fullName: string;
  prNumber: number;
}

export function CodeReviewBanner({ fullName, prNumber }: CodeReviewBannerProps) {
  const {
    review,
    active,
    loading,
    error,
    maxIssues,
    timeout,
    available,
    setMaxIssues,
    setTimeout: setStoreTimeout,
    generate,
    cancelGenerate,
    start,
  } = useCodeReviewStore();

  const elapsed = useElapsedTime(loading);
  const [maxInput, setMaxInput] = useState(String(maxIssues));
  const [timeoutInput, setTimeoutInput] = useState(String(timeout));

  if (!available) return null;
  if (active) return null;

  return (
    <div
      className={`font-sans border p-4 mb-4 border-[var(--cr-border)] bg-gradient-to-r from-[var(--cr-gradient-from)] to-[var(--cr-gradient-to)]`}
    >
      {review ? (
        <>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Code Review</h3>
            <span className="text-xs text-[var(--text-muted)]">
              {review.issues.length} issue{review.issues.length !== 1 ? 's' : ''} found
            </span>
          </div>
          <p className="text-sm text-[var(--text-secondary)] mb-3">{review.summary}</p>
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={start}
              className="px-3 py-1.5 text-xs font-semibold bg-[var(--cr-border)] text-white border-0 cursor-pointer hover:opacity-90"
            >
              Start Review
            </button>
            <button
              onClick={() => generate(fullName, prNumber)}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-medium bg-[var(--surface-1)] text-[var(--text-secondary)] border border-[var(--cr-border)] cursor-pointer hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Generating...' : 'Regenerate'}
            </button>
            {loading && (
              <span className="text-xs text-[var(--text-muted)]">
                <Spinner /> {elapsed}
              </span>
            )}
            {loading && (
              <button
                onClick={cancelGenerate}
                className="px-2 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--error-text)] bg-transparent border border-[var(--border)] cursor-pointer rounded"
              >
                Cancel
              </button>
            )}
          </div>
        </>
      ) : (
        <>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">Code Review</h3>
          <p className="text-xs text-[var(--text-secondary)] mb-3">
            Generate an AI code review for this PR. The reviewer will analyze diffs, verify assumptions
            by reading code, and surface issues with severity ratings and suggested fixes.
          </p>
          <div className="flex items-center gap-3 flex-wrap">
            <label className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              Max issues:
              <input
                type="number"
                min="1"
                max="50"
                value={maxInput}
                onChange={(e) => setMaxInput(e.target.value)}
                onBlur={() => {
                  const n = Math.max(1, Math.min(50, parseInt(maxInput) || 20));
                  setMaxInput(String(n));
                  setMaxIssues(n);
                }}
                className="w-14 px-1 py-0.5 text-xs border border-[var(--border)] bg-[var(--surface-0)] text-[var(--text-primary)] rounded"
              />
            </label>
            <label className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              Timeout:
              <input
                type="number"
                min="30"
                max="1800"
                value={timeoutInput}
                onChange={(e) => setTimeoutInput(e.target.value)}
                onBlur={() => {
                  const t = Math.max(30, Math.min(1800, parseInt(timeoutInput) || 300));
                  setTimeoutInput(String(t));
                  setStoreTimeout(t);
                }}
                className="w-16 px-1 py-0.5 text-xs border border-[var(--border)] bg-[var(--surface-0)] text-[var(--text-primary)] rounded"
              />
              <span className="text-[var(--text-muted)]">s</span>
            </label>
            <button
              onClick={() => generate(fullName, prNumber)}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-semibold bg-[var(--cr-border)] text-white border-0 cursor-pointer hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Generating...' : 'Generate Code Review'}
            </button>
            {loading && (
              <span className="text-xs text-[var(--text-muted)]">
                <Spinner /> Generating code review... {elapsed}
              </span>
            )}
            {loading && (
              <button
                onClick={cancelGenerate}
                className="px-2 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--error-text)] bg-transparent border border-[var(--border)] cursor-pointer rounded"
              >
                Cancel
              </button>
            )}
          </div>
        </>
      )}

      {error && (
        <div className="mt-3 text-xs text-[var(--error-text)] flex items-center gap-2">
          <span>{error}</span>
          <button
            onClick={() => generate(fullName, prNumber)}
            className="px-2 py-0.5 text-xs bg-transparent border border-[var(--error-text)] text-[var(--error-text)] cursor-pointer rounded hover:opacity-80"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
