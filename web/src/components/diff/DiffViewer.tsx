import { useState, useMemo } from 'react';
import { parseDiff } from 'react-diff-view';
import type { PullFile, Annotation, WalkthroughStep, CodeReviewIssue, CommentThread } from '../../api/types';
import { useCommentStore } from '../../stores/commentStore';
import { DiffFile } from './DiffFile';
import { WalkthroughStepCard } from '../walkthrough/WalkthroughStepCard';
import { CodeReviewIssueCard } from '../codereview/CodeReviewIssueCard';
import 'react-diff-view/style/index.css';

interface DiffViewerProps {
  files: PullFile[];
  annotationsByFile: Map<string, Annotation[]>;
  mode: 'inline' | 'side';
  walkthroughStep?: WalkthroughStep | null;
  walkthroughTotalSteps?: number;
  codeReviewIssue?: CodeReviewIssue | null;
  codeReviewTotalIssues?: number;
  fullName: string;
  prNumber: number;
}

function isSpecmapFile(filename: string): boolean {
  return filename.startsWith('.specmap/') || filename === '.specmap';
}

function patchToUnifiedDiff(filename: string, patch: string | undefined): string {
  if (!patch) return '';
  return `--- a/${filename}\n+++ b/${filename}\n${patch}`;
}

function renderFile(
  file: PullFile,
  annotationsByFile: Map<string, Annotation[]>,
  commentThreadsByFile: Map<string, CommentThread[]>,
  mode: 'inline' | 'side',
  index: number,
  fullName: string,
  prNumber: number,
) {
  const diffText = patchToUnifiedDiff(file.filename, file.patch);
  if (!diffText) {
    return (
      <div key={file.filename} className="bg-[var(--surface-1)] border border-[var(--border)] p-4">
        <p className="text-sm text-[var(--text-secondary)]">{file.filename}</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">Binary or empty diff</p>
      </div>
    );
  }

  const [parsed] = parseDiff(diffText, { nearbySequences: 'zip' });
  if (!parsed) return null;

  const annotations = annotationsByFile.get(file.filename) ?? [];
  const commentThreads = commentThreadsByFile.get(file.filename) ?? [];

  return (
    <DiffFile
      key={file.filename}
      file={file}
      diffData={parsed}
      annotations={annotations}
      commentThreads={commentThreads}
      mode={mode}
      fileIndex={index}
      fullName={fullName}
      prNumber={prNumber}
    />
  );
}

export function DiffViewer({ files, annotationsByFile, mode, walkthroughStep, walkthroughTotalSteps, codeReviewIssue, codeReviewTotalIssues, fullName, prNumber }: DiffViewerProps) {
  const [showSpecmap, setShowSpecmap] = useState(false);
  const threadsByFile = useCommentStore((s) => s.threadsByFile);

  const { regularFiles, specmapFiles } = useMemo(() => {
    const regular: PullFile[] = [];
    const specmap: PullFile[] = [];
    for (const f of files) {
      if (isSpecmapFile(f.filename)) {
        specmap.push(f);
      } else {
        regular.push(f);
      }
    }
    return { regularFiles: regular, specmapFiles: specmap };
  }, [files]);

  if (files.length === 0) {
    return <p className="text-[var(--text-muted)]">No files changed.</p>;
  }

  return (
    <div className="space-y-4">
      {specmapFiles.length > 0 && (
        <button
          onClick={() => setShowSpecmap(!showSpecmap)}
          className="flex items-center gap-2 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] cursor-pointer bg-[var(--surface-2)] border border-[var(--border)] px-3 py-2 hover:border-[var(--text-muted)] w-full text-left"
        >
          <span className="w-3">{showSpecmap ? '-' : '+'}</span>
          <span>
            {showSpecmap ? 'hide' : 'show'} .specmap/ directory changes
          </span>
          <span className="text-[var(--text-muted)]">
            ({specmapFiles.length} file{specmapFiles.length !== 1 ? 's' : ''})
          </span>
        </button>
      )}
      {showSpecmap &&
        specmapFiles.map((file, i) =>
          renderFile(file, annotationsByFile, threadsByFile, mode, i, fullName, prNumber),
        )}
      {regularFiles.map((file, index) => (
        <div key={file.filename}>
          {walkthroughStep?.file === file.filename && walkthroughTotalSteps && (
            <WalkthroughStepCard step={walkthroughStep} totalSteps={walkthroughTotalSteps} fullName={fullName} prNumber={prNumber} />
          )}
          {codeReviewIssue?.file === file.filename && codeReviewTotalIssues && (
            <CodeReviewIssueCard issue={codeReviewIssue} totalIssues={codeReviewTotalIssues} fullName={fullName} prNumber={prNumber} />
          )}
          {renderFile(file, annotationsByFile, threadsByFile, mode, specmapFiles.length + index, fullName, prNumber)}
        </div>
      ))}
    </div>
  );
}
