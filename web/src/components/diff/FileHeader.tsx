interface FileHeaderProps {
  filename: string;
  additions: number;
  deletions: number;
  collapsed: boolean;
  onToggle: () => void;
}

export function FileHeader({ filename, additions, deletions, collapsed, onToggle }: FileHeaderProps) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center gap-3 px-4 py-2.5 border-b border-gray-200 hover:bg-gray-50 cursor-pointer bg-transparent text-left"
    >
      <span className="text-gray-400 text-xs">{collapsed ? '+' : '-'}</span>
      <span className="font-mono text-sm text-gray-900 flex-1">{filename}</span>
      <span className="text-xs">
        {additions > 0 && <span className="text-green-600">+{additions}</span>}
        {additions > 0 && deletions > 0 && <span className="text-gray-400 mx-1">/</span>}
        {deletions > 0 && <span className="text-red-600">-{deletions}</span>}
      </span>
    </button>
  );
}
