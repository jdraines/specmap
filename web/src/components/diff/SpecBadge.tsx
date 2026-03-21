import { useState } from 'react';
import type { SpecRef } from '../../api/types';
import { useSpecPanelStore } from '../../stores/specPanelStore';

interface SpecBadgeProps {
  refId: number;
  specRef: SpecRef;
}

export function SpecBadge({ refId, specRef }: SpecBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const open = useSpecPanelStore((s) => s.open);

  return (
    <span className="relative inline-block">
      <button
        className="inline-flex items-center justify-center px-1.5 py-0 text-xs font-mono font-semibold text-blue-700 bg-blue-100 rounded hover:bg-blue-200 cursor-pointer border-0"
        onClick={() => open(specRef)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        [{refId}]
      </button>
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-50">
          <div className="font-medium">{specRef.heading}</div>
          <div className="text-gray-300 mt-1 line-clamp-3">{specRef.excerpt}</div>
        </div>
      )}
    </span>
  );
}
