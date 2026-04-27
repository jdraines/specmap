interface HunkExpanderProps {
  lineCount: number;
  onExpand: () => void;
  loading?: boolean;
}

export function HunkExpander({ lineCount, onExpand, loading }: HunkExpanderProps) {
  if (lineCount <= 0) return null;

  return (
    <button
      className="w-full text-xs text-[var(--text-secondary)] hover:text-[var(--text-secondary)] hover:bg-[var(--hover-bg)] bg-[var(--surface-2)] border-0 cursor-pointer py-1 px-2 text-center"
      onClick={(e) => {
        e.stopPropagation();
        onExpand();
      }}
      disabled={loading}
    >
      {loading ? 'loading...' : `show ${lineCount} more line${lineCount !== 1 ? 's' : ''}`}
    </button>
  );
}
