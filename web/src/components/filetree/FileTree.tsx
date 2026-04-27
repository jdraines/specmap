import { useState, useMemo, useCallback } from 'react';
import type { PullFile, Annotation } from '../../api/types';

interface TreeNode {
  name: string;
  path: string;
  children: TreeNode[];
  file: PullFile | null;
  fileIndex: number | null;
  annotationCount: number;
}

function buildTree(files: PullFile[], annotationsByFile: Map<string, Annotation[]>, fileIndexOffset: number): TreeNode {
  const root: TreeNode = { name: '', path: '', children: [], file: null, fileIndex: null, annotationCount: 0 };

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const parts = file.filename.split('/');
    let node = root;

    for (let j = 0; j < parts.length; j++) {
      const part = parts[j];
      const partPath = parts.slice(0, j + 1).join('/');
      const isLeaf = j === parts.length - 1;

      let child = node.children.find((c) => c.name === part);
      if (!child) {
        child = {
          name: part,
          path: partPath,
          children: [],
          file: isLeaf ? file : null,
          fileIndex: isLeaf ? fileIndexOffset + i : null,
          annotationCount: isLeaf ? (annotationsByFile.get(file.filename)?.length ?? 0) : 0,
        };
        node.children.push(child);
      }
      if (isLeaf) {
        child.file = file;
        child.fileIndex = fileIndexOffset + i;
        child.annotationCount = annotationsByFile.get(file.filename)?.length ?? 0;
      }
      node = child;
    }
  }

  // Collapse single-child directories: a/b/c.ts → a/b/c.ts
  function collapse(node: TreeNode): TreeNode {
    node.children = node.children.map(collapse);
    if (node.children.length === 1 && !node.file && node.name) {
      const child = node.children[0];
      if (!child.file) {
        return { ...child, name: `${node.name}/${child.name}` };
      }
    }
    return node;
  }

  return collapse(root);
}

function statusIcon(status: string): string {
  switch (status) {
    case 'added': return 'A';
    case 'removed': return 'D';
    case 'renamed': return 'R';
    default: return 'M';
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'added': return 'var(--insert-text)';
    case 'removed': return 'var(--delete-text)';
    default: return 'var(--text-muted)';
  }
}

interface TreeNodeViewProps {
  node: TreeNode;
  depth: number;
  onFileClick: (fileIndex: number) => void;
  activeFileIndex: number | null;
  commentCountByFile?: Map<string, number>;
}

function TreeNodeView({ node, depth, onFileClick, activeFileIndex, commentCountByFile }: TreeNodeViewProps) {
  const [expanded, setExpanded] = useState(true);
  const isDir = !node.file && node.children.length > 0;

  if (node.file && node.fileIndex != null) {
    const isActive = node.fileIndex === activeFileIndex;
    const commentCount = commentCountByFile?.get(node.file.filename) ?? 0;
    return (
      <button
        onClick={() => onFileClick(node.fileIndex!)}
        className={`w-full flex items-center gap-1 px-1 py-0.5 text-left text-[11px] cursor-pointer bg-transparent border-0 hover:bg-[var(--hover-bg)] ${isActive ? 'bg-[var(--hover-bg)]' : ''}`}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
        title={node.path}
      >
        <span
          className="w-3 text-center font-mono text-[10px] flex-shrink-0"
          style={{ color: statusColor(node.file.status) }}
        >
          {statusIcon(node.file.status)}
        </span>
        <span className="truncate text-[var(--text-primary)]">{node.name}</span>
        {node.annotationCount > 0 && (
          <span className="text-[9px] text-[var(--accent)] border border-[var(--accent)] px-0.5 flex-shrink-0">
            {node.annotationCount}
          </span>
        )}
        {commentCount > 0 && (
          <span className="text-[9px] text-[var(--comment-border)] border border-[var(--comment-border)] px-0.5 flex-shrink-0">
            {commentCount}
          </span>
        )}
      </button>
    );
  }

  if (isDir) {
    return (
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-1 px-1 py-0.5 text-left text-[11px] cursor-pointer bg-transparent border-0 hover:bg-[var(--hover-bg)] text-[var(--text-secondary)]"
          style={{ paddingLeft: `${depth * 12 + 4}px` }}
        >
          <span className="w-3 text-center text-[10px] flex-shrink-0">{expanded ? '\u25BE' : '\u25B8'}</span>
          <span className="truncate font-medium">{node.name}</span>
        </button>
        {expanded && node.children.map((child) => (
          <TreeNodeView
            key={child.path}
            node={child}
            depth={depth + 1}
            onFileClick={onFileClick}
            activeFileIndex={activeFileIndex}
            commentCountByFile={commentCountByFile}
          />
        ))}
      </div>
    );
  }

  return null;
}

interface FileTreeProps {
  files: PullFile[];
  annotationsByFile: Map<string, Annotation[]>;
  commentCountByFile?: Map<string, number>;
  fileIndexOffset?: number;
}

export function FileTree({ files, annotationsByFile, commentCountByFile, fileIndexOffset = 0 }: FileTreeProps) {
  const [activeFileIndex, setActiveFileIndex] = useState<number | null>(null);

  const tree = useMemo(
    () => buildTree(files, annotationsByFile, fileIndexOffset),
    [files, annotationsByFile, fileIndexOffset],
  );

  const handleFileClick = useCallback((fileIndex: number) => {
    setActiveFileIndex(fileIndex);
    const el = document.querySelector(`[data-file-index="${fileIndex}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      document.querySelectorAll('[data-file-focused]').forEach((e) => e.removeAttribute('data-file-focused'));
      el.setAttribute('data-file-focused', 'true');
    }
  }, []);

  return (
    <div className="py-1">
      <div className="px-2 py-1 text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">
        Changed files ({files.length})
      </div>
      {tree.children.map((child) => (
        <TreeNodeView
          key={child.path}
          node={child}
          depth={0}
          onFileClick={handleFileClick}
          activeFileIndex={activeFileIndex}
          commentCountByFile={commentCountByFile}
        />
      ))}
    </div>
  );
}
