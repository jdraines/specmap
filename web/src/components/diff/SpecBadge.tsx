import { useState, useRef, useCallback } from 'react';
import type { SpecRef } from '../../api/types';
import { useSpecPanelStore } from '../../stores/specPanelStore';
import { SpecTooltip } from '../spec/SpecTooltip';

function specName(path: string): string {
  const parts = path.split('/');
  return parts[parts.length - 1];
}

interface SpecBadgeProps {
  refId: number;
  specRef: SpecRef;
}

export function SpecBadge({ refId: _refId, specRef }: SpecBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 });
  const badgeRef = useRef<HTMLButtonElement>(null);
  const hideTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);
  const openModal = useSpecPanelStore((s) => s.openModal);

  const show = useCallback(() => {
    clearTimeout(hideTimeout.current);
    hideTimeout.current = setTimeout(() => {
      if (badgeRef.current) {
        const rect = badgeRef.current.getBoundingClientRect();
        setTooltipPos({
          top: rect.bottom + 4,
          left: rect.left + rect.width / 2,
        });
      }
      setShowTooltip(true);
    }, 200);
  }, []);

  const hide = useCallback(() => {
    clearTimeout(hideTimeout.current);
    hideTimeout.current = setTimeout(() => setShowTooltip(false), 150);
  }, []);

  const keep = useCallback(() => {
    clearTimeout(hideTimeout.current);
  }, []);

  return (
    <>
      <button
        ref={badgeRef}
        className="inline-flex items-center gap-1 px-1.5 py-0 text-xs bg-[var(--badge-bg)] text-[var(--badge-text)] hover:opacity-80 cursor-pointer border-0"
        onClick={() => openModal(specRef)}
        onMouseEnter={show}
        onMouseLeave={hide}
      >
        {specName(specRef.spec_file)}
      </button>
      {showTooltip && (
        <SpecTooltip
          heading={specRef.heading}
          excerpt={specRef.excerpt}
          position={tooltipPos}
          onMouseEnter={keep}
          onMouseLeave={hide}
        />
      )}
    </>
  );
}
