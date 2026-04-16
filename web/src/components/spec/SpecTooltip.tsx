import { createPortal } from 'react-dom';

interface SpecTooltipProps {
  heading: string;
  excerpt: string;
  position: { top: number; left: number };
  placement: 'above' | 'below';
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function SpecTooltip({ heading, excerpt, position, placement, onMouseEnter, onMouseLeave }: SpecTooltipProps) {
  return createPortal(
    <div
      className="fixed z-[9999] w-72 p-3 bg-[var(--surface-1)] border border-[var(--border)] shadow-lg text-xs"
      style={{
        top: position.top,
        left: position.left,
        transform: placement === 'above' ? 'translateX(-50%) translateY(-100%)' : 'translateX(-50%)',
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="font-semibold text-[var(--text-primary)] mb-1">{heading}</div>
      <div className="text-[var(--text-secondary)] line-clamp-4 leading-relaxed">{excerpt}</div>
    </div>,
    document.body,
  );
}
