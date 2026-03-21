import { useState, useMemo } from 'react';
import { Diff, Hunk, getChangeKey } from 'react-diff-view';
import type { FileData, HunkData, ChangeData } from 'react-diff-view';
import type { PullFile, Annotation } from '../../api/types';
import { FileHeader } from './FileHeader';
import { AnnotationWidget } from './AnnotationWidget';

interface DiffFileProps {
  file: PullFile;
  diffData: FileData;
  annotations: Annotation[];
}

function findChangeForLine(hunks: HunkData[], line: number): ChangeData | null {
  for (const hunk of hunks) {
    for (const change of hunk.changes) {
      const changeLine =
        change.type === 'delete'
          ? change.lineNumber
          : change.type === 'insert'
            ? change.lineNumber
            : change.newLineNumber;
      if (changeLine === line) return change;
    }
  }
  return null;
}

export function DiffFile({ file, diffData, annotations }: DiffFileProps) {
  const [collapsed, setCollapsed] = useState(false);

  // Build widgets map: for each annotation, attach to the first visible line in the hunk.
  const { widgets, unmatchedAnnotations } = useMemo(() => {
    const w: Record<string, React.ReactNode> = {};
    const unmatched: Annotation[] = [];

    for (const ann of annotations) {
      let placed = false;
      // Try each line in the annotation range.
      for (let line = ann.start_line; line <= ann.end_line; line++) {
        const change = findChangeForLine(diffData.hunks, line);
        if (change) {
          const key = getChangeKey(change);
          // Don't overwrite — append multiple annotations for the same line.
          if (w[key]) {
            w[key] = (
              <>
                {w[key]}
                <AnnotationWidget annotation={ann} />
              </>
            );
          } else {
            w[key] = <AnnotationWidget annotation={ann} />;
          }
          placed = true;
          break;
        }
      }
      if (!placed) {
        unmatched.push(ann);
      }
    }

    return { widgets: w, unmatchedAnnotations: unmatched };
  }, [annotations, diffData.hunks]);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <FileHeader
        filename={file.filename}
        additions={file.additions}
        deletions={file.deletions}
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
      />
      {!collapsed && (
        <>
          {unmatchedAnnotations.length > 0 && (
            <div className="border-b border-gray-100 px-4 py-2 bg-amber-50">
              <p className="text-xs text-amber-700 font-medium mb-1">
                Annotations outside visible hunks:
              </p>
              {unmatchedAnnotations.map((ann) => (
                <AnnotationWidget key={ann.id} annotation={ann} />
              ))}
            </div>
          )}
          <div className="overflow-x-auto text-sm">
            <Diff viewType="unified" diffType={diffData.type} hunks={diffData.hunks} widgets={widgets}>
              {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
            </Diff>
          </div>
        </>
      )}
    </div>
  );
}
