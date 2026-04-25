import { useCodeReviewStore } from '../../stores/codeReviewStore';

const severityColor: Record<string, string> = {
  P0: 'var(--cr-p0)',
  P1: 'var(--cr-p1)',
  P2: 'var(--cr-p2)',
  P3: 'var(--cr-p3)',
  P4: 'var(--cr-p4)',
};

export function CodeReviewNav() {
  const { review, active, currentIssue, nextIssue, prevIssue, exit } = useCodeReviewStore();

  if (!active || !review) return null;

  const total = review.issues.length;
  const issue = review.issues[currentIssue];

  return (
    <div className="font-sans fixed bottom-0 left-0 right-0 z-[9000] bg-[var(--cr-nav-bg)] border-t border-[var(--cr-border)] px-4 py-2.5 flex items-center gap-3 shadow-[0_-4px_20px_rgba(234,88,12,0.3)]">
      {/* Severity-colored dots */}
      <div className="flex gap-1">
        {review.issues.map((iss, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full cursor-pointer ${
              i === currentIssue ? 'ring-1 ring-white ring-offset-1 ring-offset-[var(--cr-nav-bg)]' : ''
            }`}
            style={{
              backgroundColor: severityColor[iss.severity] || 'var(--cr-nav-dot)',
              opacity: i === currentIssue ? 1 : 0.7,
            }}
            onClick={() => useCodeReviewStore.getState().goToIssue(i)}
          />
        ))}
      </div>

      <span className="text-xs text-[var(--cr-nav-text)] opacity-60 whitespace-nowrap">
        Issue {currentIssue + 1} of {total}
      </span>

      {issue && (
        <span className="text-xs font-medium text-[var(--cr-nav-text)] truncate flex-1 min-w-0 flex items-center gap-1.5">
          <span
            className="inline-block px-1 py-0 text-[10px] font-bold rounded"
            style={{ backgroundColor: severityColor[issue.severity] || 'var(--cr-nav-dot)', color: 'white' }}
          >
            {issue.severity}
          </span>
          {issue.title}
        </span>
      )}

      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={prevIssue}
          disabled={currentIssue === 0}
          className="px-2 py-1 text-xs font-medium bg-transparent text-[var(--cr-nav-text)] border border-[var(--cr-nav-dot)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--cr-nav-dot)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <button
          onClick={nextIssue}
          disabled={currentIssue >= total - 1}
          className="px-2 py-1 text-xs font-medium bg-transparent text-[var(--cr-nav-text)] border border-[var(--cr-nav-dot)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--cr-nav-dot)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
        <button
          onClick={exit}
          className="px-2 py-1 text-xs text-[var(--cr-nav-text)] opacity-60 hover:opacity-100 bg-transparent border-0 cursor-pointer"
        >
          Exit
        </button>
      </div>
    </div>
  );
}
