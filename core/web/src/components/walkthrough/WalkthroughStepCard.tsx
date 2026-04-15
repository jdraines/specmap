import type { WalkthroughStep } from '../../api/types';
import { useWalkthroughStore } from '../../stores/walkthroughStore';
import { SpecBadge } from '../diff/SpecBadge';

interface WalkthroughStepCardProps {
  step: WalkthroughStep;
  totalSteps: number;
}

function renderNarrative(text: string): React.ReactNode[] {
  // Split on [N] references and render inline
  const parts = text.split(/(\[(\d+)\])/g);
  const nodes: React.ReactNode[] = [];
  let i = 0;
  while (i < parts.length) {
    if (i + 2 < parts.length && parts[i + 1] && /^\[\d+\]$/.test(parts[i + 1])) {
      nodes.push(<span key={i}>{parts[i]}</span>);
      nodes.push(
        <span
          key={`ref-${i}`}
          className="inline-flex items-center px-1 py-0 text-xs bg-[var(--badge-bg)] text-[var(--badge-text)]"
        >
          {parts[i + 1]}
        </span>,
      );
      i += 3;
    } else {
      nodes.push(<span key={i}>{parts[i]}</span>);
      i += 1;
    }
  }
  return nodes;
}

export function WalkthroughStepCard({ step, totalSteps }: WalkthroughStepCardProps) {
  const { nextStep, prevStep, exit, currentStep } = useWalkthroughStore();

  return (
    <div
      className="border-l-4 border-l-[var(--accent)] border border-[var(--border)] bg-[var(--surface-2)] p-4 mb-2"
      data-walkthrough-step={step.step_number}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-[var(--text-muted)]">
          Step {step.step_number} of {totalSteps}
        </span>
        <button
          onClick={exit}
          className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] bg-transparent border-0 cursor-pointer"
        >
          exit walkthrough
        </button>
      </div>

      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">{step.title}</h3>

      <div className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">
        {renderNarrative(step.narrative)}
      </div>

      {step.refs.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {step.refs.map((ref) => (
            <SpecBadge key={ref.id} refId={ref.id} specRef={ref} />
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={prevStep}
          disabled={currentStep === 0}
          className="px-2 py-1 text-xs bg-[var(--surface-1)] text-[var(--text-secondary)] border border-[var(--border)] cursor-pointer hover:border-[var(--text-muted)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <button
          onClick={nextStep}
          disabled={currentStep >= totalSteps - 1}
          className="px-2 py-1 text-xs bg-[var(--surface-1)] text-[var(--text-secondary)] border border-[var(--border)] cursor-pointer hover:border-[var(--text-muted)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  );
}
