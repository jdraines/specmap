interface FileHeaderProps {
  filename: string;
  additions: number;
  deletions: number;
  collapsed: boolean;
  onToggle: () => void;
  annotationCount?: number;
}

export function FileHeader({ filename, additions, deletions, collapsed, onToggle, annotationCount }: FileHeaderProps) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center gap-3 px-4 py-2 border-b border-[var(--border)] hover:bg-[var(--hover-bg)] cursor-pointer bg-transparent text-left"
    >
      <span className="text-[var(--text-secondary)] text-xs w-3">{collapsed ? '+' : '-'}</span>
      <span className="text-sm text-[var(--text-primary)] flex-1 truncate">{filename}</span>
      {annotationCount != null && annotationCount > 0 && (
        <span className="text-[10px] text-[var(--accent)] border border-[var(--accent)] px-1 py-0">
          {annotationCount}
        </span>
      )}
      <span className="text-xs tabular-nums">
        {additions > 0 && <span className="text-[var(--insert-text)]">+{additions}</span>}
        {additions > 0 && deletions > 0 && <span className="text-[var(--text-secondary)] mx-0.5">/</span>}
        {deletions > 0 && <span className="text-[var(--delete-text)]">-{deletions}</span>}
      </span>
    </button>
  );
}
