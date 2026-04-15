import { useWalkthroughStore } from '../../stores/walkthroughStore';

export function WalkthroughNav() {
  const { walkthrough, active, currentStep, nextStep, prevStep, exit } = useWalkthroughStore();

  if (!active || !walkthrough) return null;

  const total = walkthrough.steps.length;
  const step = walkthrough.steps[currentStep];

  return (
    <div className="font-sans fixed bottom-0 left-0 right-0 z-[9000] bg-[var(--wt-nav-bg)] border-t border-[var(--wt-border)] px-4 py-2 flex items-center gap-3">
      {/* Progress dots */}
      <div className="flex gap-1">
        {walkthrough.steps.map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full cursor-pointer ${
              i === currentStep
                ? 'bg-[var(--wt-nav-dot)]'
                : i < currentStep
                  ? 'bg-[var(--wt-nav-dot)] opacity-40'
                  : 'bg-[var(--wt-nav-dot-inactive)]'
            }`}
            onClick={() => useWalkthroughStore.getState().goToStep(i)}
          />
        ))}
      </div>

      <span className="text-xs text-[var(--wt-nav-text)] opacity-60 whitespace-nowrap">
        Step {currentStep + 1} of {total}
      </span>

      <span className="text-xs text-[var(--wt-nav-text)] truncate flex-1 min-w-0">
        {step?.title}
      </span>

      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={prevStep}
          disabled={currentStep === 0}
          className="px-2 py-1 text-xs bg-transparent text-[var(--wt-nav-text)] border border-[var(--wt-nav-dot)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--wt-nav-dot)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <button
          onClick={nextStep}
          disabled={currentStep >= total - 1}
          className="px-2 py-1 text-xs bg-transparent text-[var(--wt-nav-text)] border border-[var(--wt-nav-dot)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--wt-nav-dot)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
        <button
          onClick={exit}
          className="px-2 py-1 text-xs text-[var(--wt-nav-text)] opacity-60 hover:opacity-100 bg-transparent border-0 cursor-pointer"
        >
          Exit
        </button>
      </div>
    </div>
  );
}
