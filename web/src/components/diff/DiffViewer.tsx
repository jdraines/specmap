import { parseDiff } from 'react-diff-view';
import type { PullFile, Annotation } from '../../api/types';
import { DiffFile } from './DiffFile';
import 'react-diff-view/style/index.css';

interface DiffViewerProps {
  files: PullFile[];
  annotationsByFile: Map<string, Annotation[]>;
}

function patchToUnifiedDiff(filename: string, patch: string | undefined): string {
  if (!patch) return '';
  // GitHub's patch field lacks --- / +++ headers. Synthesize them so
  // parseDiff (which delegates to gitdiff-parser) can parse it.
  return `--- a/${filename}\n+++ b/${filename}\n${patch}`;
}

export function DiffViewer({ files, annotationsByFile }: DiffViewerProps) {
  if (files.length === 0) {
    return <p className="text-gray-500">No files changed.</p>;
  }

  return (
    <div className="space-y-6">
      {files.map((file) => {
        const diffText = patchToUnifiedDiff(file.filename, file.patch);
        if (!diffText) {
          return (
            <div key={file.filename} className="bg-white rounded-lg border border-gray-200 p-4">
              <p className="font-mono text-sm text-gray-600">{file.filename}</p>
              <p className="text-sm text-gray-400 mt-1">Binary or empty diff</p>
            </div>
          );
        }

        const [parsed] = parseDiff(diffText, { nearbySequences: 'zip' });
        if (!parsed) return null;

        const annotations = annotationsByFile.get(file.filename) ?? [];

        return (
          <DiffFile
            key={file.filename}
            file={file}
            diffData={parsed}
            annotations={annotations}
          />
        );
      })}
    </div>
  );
}
