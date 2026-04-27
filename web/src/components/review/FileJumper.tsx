import { useState, useRef, useEffect } from 'react';
import type { PullFile, Annotation } from '../../api/types';

interface FileJumperProps {
  files: PullFile[];
  annotationsByFile: Map<string, Annotation[]>;
}

export function FileJumper({ files, annotationsByFile }: FileJumperProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleJump = (filename: string) => {
    const el = document.querySelector(`[data-file="${CSS.escape(filename)}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="px-2 py-0.5 text-xs cursor-pointer border border-[var(--border)] bg-transparent text-[var(--text-secondary)] hover:border-[var(--text-muted)]"
      >
        jump [{files.length}]
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 w-80 max-h-64 overflow-y-auto bg-[var(--surface-1)] border border-[var(--border)] shadow-lg z-50 text-xs">
          {files.map((f) => {
            const annCount = annotationsByFile.get(f.filename)?.length ?? 0;
            return (
              <button
                key={f.filename}
                onClick={() => handleJump(f.filename)}
                className="w-full text-left px-3 py-1.5 hover:bg-[var(--hover-bg)] cursor-pointer bg-transparent border-0 flex items-center gap-2"
              >
                <span className="flex-1 truncate text-[var(--text-primary)]">{f.filename}</span>
                {annCount > 0 && (
                  <span className="text-[var(--accent)] whitespace-nowrap">{annCount}</span>
                )}
                <span className="whitespace-nowrap text-[var(--text-secondary)] tabular-nums">
                  <span className="text-[var(--insert-text)]">+{f.additions}</span>
                  <span className="mx-0.5">/</span>
                  <span className="text-[var(--delete-text)]">-{f.deletions}</span>
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
