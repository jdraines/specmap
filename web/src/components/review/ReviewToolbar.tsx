import { useLayoutStore } from '../../stores/layoutStore';
import { FileJumper } from './FileJumper';
import type { Annotation } from '../../api/types';
import type { PullFile } from '../../api/types';

interface ReviewToolbarProps {
  annotations: Annotation[];
  files: PullFile[];
  annotationsByFile: Map<string, Annotation[]>;
}

export function ReviewToolbar({ annotations, files, annotationsByFile }: ReviewToolbarProps) {
  const { annotationMode, setAnnotationMode, fileTreeOpen, toggleFileTree } = useLayoutStore();

  const annotationCount = annotations.length;
  const annotatedFiles = new Set(annotations.map((a) => a.file)).size;

  return (
    <div className="flex items-center justify-between py-2 mb-4 border-b border-[var(--border)] text-xs">
      <div className="flex items-center gap-3">
        <span className="text-[var(--text-secondary)]">
          {annotationCount} annotation{annotationCount !== 1 ? 's' : ''} across{' '}
          {annotatedFiles} file{annotatedFiles !== 1 ? 's' : ''}
          <span className="text-[var(--text-muted)]"> &middot; {files.length} changed</span>
        </span>
        <FileJumper files={files} annotationsByFile={annotationsByFile} />
        <button
          onClick={toggleFileTree}
          className={`px-2 py-0.5 text-xs cursor-pointer border ${
            fileTreeOpen
              ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
              : 'bg-transparent text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--text-muted)]'
          }`}
          title="Toggle file tree (b)"
        >
          tree
        </button>
      </div>
      <div className="flex items-center gap-1">
        <span className="text-[var(--text-muted)] mr-2">layout:</span>
        {(['inline', 'auto', 'side'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setAnnotationMode(mode)}
            className={`px-2 py-0.5 text-xs cursor-pointer border ${
              annotationMode === mode
                ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                : 'bg-transparent text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--text-muted)]'
            }`}
          >
            {mode}
          </button>
        ))}
        <span className="text-[var(--text-muted)] ml-3">
          <kbd className="px-1 py-0.5 border border-[var(--kbd-border)] bg-[var(--kbd-bg)] text-[10px]">?</kbd> keys
        </span>
      </div>
    </div>
  );
}
