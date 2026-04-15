import { useWalkthroughStore } from '../../stores/walkthroughStore';

export function WalkthroughNav() {
  const { walkthrough, active, currentStep, nextStep, prevStep, exit } = useWalkthroughStore();

  if (!active || !walkthrough) return null;

  const total = walkthrough.steps.length;
  const step = walkthrough.steps[currentStep];

  return (
    <div className="fixed bottom-0 left-0 right-0 z-[9000] bg-[var(--surface-1)] border-t border-[var(--border)] px-4 py-2 flex items-center gap-3">
      {/* Progress bar */}
      <div className="flex gap-1">
        {walkthrough.steps.map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full cursor-pointer ${
              i === currentStep
                ? 'bg-[var(--accent)]'
                : i < currentStep
                  ? 'bg-[var(--accent)] opacity-40'
                  : 'bg-[var(--border)]'
            }`}
            onClick={() => useWalkthroughStore.getState().goToStep(i)}
          />
        ))}
      </div>

      <span className="text-xs text-[var(--text-muted)] whitespace-nowrap">
        Step {currentStep + 1} of {total}
      </span>

      <span className="text-xs text-[var(--text-secondary)] truncate flex-1 min-w-0">
        {step?.title}
      </span>

      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={prevStep}
          disabled={currentStep === 0}
          className="px-2 py-1 text-xs bg-[var(--surface-2)] text-[var(--text-secondary)] border border-[var(--border)] cursor-pointer hover:border-[var(--text-muted)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <button
          onClick={nextStep}
          disabled={currentStep >= total - 1}
          className="px-2 py-1 text-xs bg-[var(--surface-2)] text-[var(--text-secondary)] border border-[var(--border)] cursor-pointer hover:border-[var(--text-muted)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
        <button
          onClick={exit}
          className="px-2 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] bg-transparent border-0 cursor-pointer"
        >
          Exit
        </button>
      </div>
    </div>
  );
}
