import type { WalkthroughStep } from '../../api/types';
import { useWalkthroughStore } from '../../stores/walkthroughStore';
import { SpecBadge } from '../diff/SpecBadge';
import { StepChat } from './StepChat';

interface WalkthroughStepCardProps {
  step: WalkthroughStep;
  totalSteps: number;
  fullName: string;
  prNumber: number;
}

export function renderTextWithBold(text: string, keyPrefix: string): React.ReactNode[] {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${keyPrefix}-b${i}`}>{part.slice(2, -2)}</strong>;
    }
    return <span key={`${keyPrefix}-${i}`}>{part}</span>;
  });
}

function renderNarrative(text: string): React.ReactNode[] {
  // Split on [N] references and render inline
  const parts = text.split(/(\[(\d+)\])/g);
  const nodes: React.ReactNode[] = [];
  let i = 0;
  while (i < parts.length) {
    if (i + 2 < parts.length && parts[i + 1] && /^\[\d+\]$/.test(parts[i + 1])) {
      nodes.push(...renderTextWithBold(parts[i], String(i)));
      nodes.push(
        <span
          key={`ref-${i}`}
          className="inline-flex items-center px-1 py-0 text-xs font-mono bg-[var(--badge-bg)] text-[var(--badge-text)]"
        >
          {parts[i + 1]}
        </span>,
      );
      i += 3;
    } else {
      nodes.push(...renderTextWithBold(parts[i], String(i)));
      i += 1;
    }
  }
  return nodes;
}

export function WalkthroughStepCard({ step, totalSteps, fullName, prNumber }: WalkthroughStepCardProps) {
  const { nextStep, prevStep, exit, currentStep } = useWalkthroughStore();

  return (
    <div
      className="font-sans border-l-4 border-l-[var(--wt-border)] border border-[var(--border)] bg-gradient-to-r from-[var(--wt-gradient-from)] to-[var(--wt-gradient-to)] p-4 mb-2"
      data-walkthrough-step={step.step_number}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="inline-flex items-center gap-2 text-xs">
          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-[var(--wt-step-num-bg)] text-[var(--wt-step-num-text)] text-[10px] font-semibold">
            {step.step_number}
          </span>
          <span className="font-medium text-[var(--text-muted)]">of {totalSteps}</span>
        </span>
        <button
          onClick={exit}
          className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] bg-transparent border-0 cursor-pointer"
        >
          exit walkthrough
        </button>
      </div>

      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">{step.title}</h3>

      <div className="text-sm font-medium text-[var(--text-primary)] leading-relaxed mb-3">
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
          className="px-2 py-1 text-xs font-medium bg-[var(--surface-1)] text-[var(--text-secondary)] border border-[var(--wt-border)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--wt-border)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <button
          onClick={nextStep}
          disabled={currentStep >= totalSteps - 1}
          className="px-2 py-1 text-xs font-medium bg-[var(--surface-1)] text-[var(--text-secondary)] border border-[var(--wt-border)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--wt-border)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>

      <StepChat step={step} fullName={fullName} prNumber={prNumber} />
    </div>
  );
}
