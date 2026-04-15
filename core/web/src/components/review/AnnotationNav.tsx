import { useEffect, useState, useCallback } from 'react';
import type { Annotation } from '../../api/types';

interface AnnotationNavProps {
  annotations: Annotation[];
}

export function AnnotationNav({ annotations }: AnnotationNavProps) {
  const [positions, setPositions] = useState<{ id: string; pct: number }[]>([]);

  useEffect(() => {
    function calculate() {
      const docHeight = document.documentElement.scrollHeight;
      if (docHeight === 0 || annotations.length === 0) {
        setPositions([]);
        return;
      }

      const result: { id: string; pct: number }[] = [];
      for (const ann of annotations) {
        const el = document.querySelector(`[data-annotation-id="${CSS.escape(ann.id)}"]`);
        if (el) {
          const rect = el.getBoundingClientRect();
          const absTop = rect.top + window.scrollY;
          result.push({ id: ann.id, pct: (absTop / docHeight) * 100 });
        }
      }
      setPositions(result);
    }

    calculate();
    window.addEventListener('resize', calculate);
    const timer = setTimeout(calculate, 500);
    return () => {
      window.removeEventListener('resize', calculate);
      clearTimeout(timer);
    };
  }, [annotations]);

  const handleClick = useCallback((id: string) => {
    const el = document.querySelector(`[data-annotation-id="${CSS.escape(id)}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, []);

  if (annotations.length === 0) return null;

  return (
    <div className="fixed right-1 top-14 bottom-0 w-3 z-50">
      {positions.map(({ id, pct }) => (
        <button
          key={id}
          onClick={() => handleClick(id)}
          className="absolute w-2 h-2 rounded-full bg-[var(--minimap-dot)] hover:scale-150 transition-transform cursor-pointer border-0 p-0 right-0 opacity-60 hover:opacity-100"
          style={{ top: `${pct}%` }}
          title="Jump to annotation"
        />
      ))}
    </div>
  );
}
