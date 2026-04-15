import { useWalkthroughStore } from '../../stores/walkthroughStore';
import { renderTextWithBold } from './WalkthroughStepCard';
import { Spinner } from '../ui/Spinner';

interface WalkthroughBannerProps {
  fullName: string;
  prNumber: number;
  hasAnnotations: boolean;
}

const familiarityOptions = [
  { value: 1, label: 'unfamiliar' },
  { value: 2, label: 'somewhat' },
  { value: 3, label: 'expert' },
] as const;

const depthOptions = [
  { value: 'quick' as const, label: 'quick overview' },
  { value: 'thorough' as const, label: 'thorough' },
] as const;

export function WalkthroughBanner({ fullName, prNumber, hasAnnotations }: WalkthroughBannerProps) {
  const {
    walkthrough,
    active,
    loading,
    error,
    familiarity,
    depth,
    available,
    setFamiliarity,
    setDepth,
    generate,
    start,
  } = useWalkthroughStore();

  if (!available || !hasAnnotations) return null;
  if (active) return null;

  return (
    <div
      className={`font-sans border p-4 mb-4 ${
        walkthrough
          ? 'border-[var(--wt-border)] bg-gradient-to-r from-[var(--wt-gradient-from)] to-[var(--wt-gradient-to)]'
          : 'border-[var(--wt-border)] bg-gradient-to-r from-[var(--wt-gradient-from)] to-[var(--wt-gradient-to)]'
      }`}
    >
      {walkthrough ? (
        <>
          <p className="text-sm text-[var(--text-primary)] mb-3">{renderTextWithBold(walkthrough.summary, 'summary')}</p>
          <div className="flex items-center gap-3">
            <button
              onClick={start}
              className="px-3 py-1.5 text-xs font-semibold bg-[var(--accent)] text-white border-0 cursor-pointer hover:opacity-90"
            >
              Start Walkthrough ({walkthrough.steps.length} steps)
            </button>
            <span className="text-xs text-[var(--text-muted)]">
              {familiarityOptions.find((o) => o.value === walkthrough.familiarity)?.label} · {walkthrough.depth}
            </span>
          </div>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-[var(--text-secondary)] mb-3">
            Get a guided walkthrough of this PR tailored to your familiarity with the codebase.
          </p>

          <div className="flex flex-wrap items-center gap-4 mb-3">
            <div className="flex items-center gap-1">
              <span className="text-xs font-semibold text-[var(--text-secondary)] mr-1">familiarity:</span>
              {familiarityOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setFamiliarity(opt.value)}
                  className={`px-2 py-1 text-xs font-medium border cursor-pointer ${
                    familiarity === opt.value
                      ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                      : 'bg-[var(--surface-1)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--text-muted)]'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1">
              <span className="text-xs font-semibold text-[var(--text-secondary)] mr-1">depth:</span>
              {depthOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setDepth(opt.value)}
                  className={`px-2 py-1 text-xs font-medium border cursor-pointer ${
                    depth === opt.value
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
              onClick={() => generate(fullName, prNumber)}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-semibold bg-[var(--accent)] text-white border-0 cursor-pointer hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Generating...' : 'Generate Walkthrough'}
            </button>
            {loading && (
              <span className="text-xs text-[var(--text-muted)]">
                <Spinner /> Generating walkthrough...
              </span>
            )}
          </div>

          {error && (
            <div className="mt-2 flex items-center gap-2">
              <p className="text-xs text-[var(--error-text)]">{error}</p>
              <button
                onClick={() => generate(fullName, prNumber)}
                className="text-xs text-[var(--accent-text)] bg-transparent border-0 cursor-pointer underline"
              >
                retry
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
