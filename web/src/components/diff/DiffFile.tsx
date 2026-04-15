import { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { useParams } from 'react-router';
import { Diff, Hunk, Decoration, getChangeKey, useSourceExpansion } from 'react-diff-view';
import type { FileData, HunkData, ChangeData } from 'react-diff-view';
import type { PullFile, Annotation } from '../../api/types';
import { pulls } from '../../api/endpoints';
import { FileHeader } from './FileHeader';
import { AnnotationWidget } from './AnnotationWidget';
import { SideAnnotation } from './SideAnnotation';
import { HunkExpander } from './HunkExpander';
import { useAnnotationPositions } from '../../hooks/useAnnotationPositions';
import { useAnnotationSpacers } from '../../hooks/useAnnotationSpacers';

interface DiffFileProps {
  file: PullFile;
  diffData: FileData;
  annotations: Annotation[];
  mode: 'inline' | 'side';
  fileIndex: number;
}

function findChangeForLine(hunks: HunkData[], line: number): ChangeData | null {
  for (const hunk of hunks) {
    for (const change of hunk.changes) {
      if (change.type === 'delete') continue;
      const changeLine =
        change.type === 'insert'
          ? change.lineNumber
          : change.newLineNumber;
      if (changeLine === line) return change;
    }
  }
  return null;
}

export function DiffFile({ file, diffData, annotations, mode, fileIndex }: DiffFileProps) {
  const { owner, repo, number } = useParams<{ owner: string; repo: string; number: string }>();
  const [collapsed, setCollapsed] = useState(false);
  const [hoveredAnnId, setHoveredAnnId] = useState<string | null>(null);
  const [oldSource, setOldSource] = useState<string | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const pendingExpand = useRef<[number, number] | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const isNewFile = file.status === 'added';
  const [renderingHunks, expandRange] = useSourceExpansion(diffData.hunks, oldSource);

  // Apply pending expansion after source loads
  useEffect(() => {
    if (oldSource !== null && pendingExpand.current) {
      const [s, e] = pendingExpand.current;
      pendingExpand.current = null;
      expandRange(s, e);
    }
  });

  const handleExpand = useCallback(
    async (start: number, end: number) => {
      if (oldSource !== null) {
        expandRange(start, end);
        return;
      }
      if (!owner || !repo || !number) return;
      pendingExpand.current = [start, end];
      setSourceLoading(true);
      try {
        const { content } = await pulls.fileSource(owner, repo, Number(number), file.filename);
        setOldSource(content);
      } catch {
        pendingExpand.current = null;
      } finally {
        setSourceLoading(false);
      }
    },
    [oldSource, expandRange, owner, repo, number, file.filename],
  );

  // Map: annotation id → change keys for all lines in its range
  const annToChangeKeys = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const ann of annotations) {
      const keys: string[] = [];
      for (let line = ann.start_line; line <= ann.end_line; line++) {
        const change = findChangeForLine(renderingHunks, line);
        if (change) keys.push(getChangeKey(change));
      }
      map.set(ann.id, keys);
    }
    return map;
  }, [annotations, renderingHunks]);

  // Reverse map: change key → annotation id
  const changeKeyToAnn = useMemo(() => {
    const map = new Map<string, string>();
    for (const [annId, keys] of annToChangeKeys) {
      for (const key of keys) {
        map.set(key, annId);
      }
    }
    return map;
  }, [annToChangeKeys]);

  const handleMouseOver = useCallback(
    (e: React.MouseEvent) => {
      const annEl = (e.target as HTMLElement).closest('[data-annotation-id]');
      if (annEl) {
        setHoveredAnnId(annEl.getAttribute('data-annotation-id'));
        return;
      }
      const tr = (e.target as HTMLElement).closest('tr[id]');
      if (tr) {
        const annId = changeKeyToAnn.get(tr.getAttribute('id')!);
        if (annId) {
          setHoveredAnnId(annId);
          return;
        }
      }
      setHoveredAnnId(null);
    },
    [changeKeyToAnn],
  );

  const handleMouseLeave = useCallback(() => setHoveredAnnId(null), []);

  // Apply/remove highlight classes on <tr> elements and annotation elements via DOM
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.querySelectorAll('.ann-line-hl').forEach((el) => el.classList.remove('ann-line-hl'));
    container.querySelectorAll('[data-ann-hover]').forEach((el) => el.removeAttribute('data-ann-hover'));

    if (!hoveredAnnId) {
      container.removeAttribute('data-has-hover');
      return;
    }

    container.setAttribute('data-has-hover', 'true');

    const keys = annToChangeKeys.get(hoveredAnnId) ?? [];
    for (const key of keys) {
      const tr = container.querySelector(`[id="${CSS.escape(key)}"]`);
      if (tr) tr.classList.add('ann-line-hl');
    }

    const annEl = container.querySelector(`[data-annotation-id="${CSS.escape(hoveredAnnId)}"]`);
    if (annEl) annEl.setAttribute('data-ann-hover', 'true');
  }, [hoveredAnnId, annToChangeKeys]);

  const { widgets, unmatchedAnnotations } = useMemo(() => {
    if (mode === 'side') return { widgets: {}, unmatchedAnnotations: [] as Annotation[] };

    const w: Record<string, React.ReactNode> = {};
    const unmatched: Annotation[] = [];

    for (const ann of annotations) {
      let placed = false;
      for (let line = ann.start_line; line <= ann.end_line; line++) {
        const change = findChangeForLine(renderingHunks, line);
        if (change) {
          const key = getChangeKey(change);
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
  }, [annotations, renderingHunks, mode]);

  const sideResult = useAnnotationPositions(annotations, renderingHunks, mode, containerRef);

  const spacerWidgets = useAnnotationSpacers(annotations, renderingHunks, mode, containerRef, sideResult.measuredHeightsRef, sideResult.heightsVersion);

  const renderHunksWithExpanders = useCallback(
    (hunks: HunkData[]) => {
      if (isNewFile || hunks.length === 0) {
        return hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />);
      }

      const elements: React.ReactElement[] = [];

      hunks.forEach((hunk, i) => {
        // Gap before this hunk
        if (i === 0) {
          // Top-of-file gap
          if (hunk.oldStart > 1) {
            const gapLines = hunk.oldStart - 1;
            elements.push(
              <Decoration key="expand-top">
                <HunkExpander
                  lineCount={gapLines}
                  onExpand={() => handleExpand(1, hunk.oldStart)}
                  loading={sourceLoading}
                />
              </Decoration>,
            );
          }
        } else {
          // Gap between previous hunk and this one
          const prevHunk = hunks[i - 1];
          const gapStart = prevHunk.oldStart + prevHunk.oldLines;
          const gapEnd = hunk.oldStart - 1;
          if (gapEnd >= gapStart) {
            elements.push(
              <Decoration key={`expand-${gapStart}`}>
                <HunkExpander
                  lineCount={gapEnd - gapStart + 1}
                  onExpand={() => handleExpand(gapStart, gapEnd + 1)}
                  loading={sourceLoading}
                />
              </Decoration>,
            );
          }
        }

        elements.push(<Hunk key={hunk.content} hunk={hunk} />);
      });

      return elements;
    },
    [isNewFile, handleExpand, sourceLoading],
  );

  return (
    <div
      className="bg-[var(--surface-1)] border border-[var(--border)]"
      data-file={file.filename}
      data-file-index={fileIndex}
    >
      <FileHeader
        filename={file.filename}
        additions={file.additions}
        deletions={file.deletions}
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
        annotationCount={annotations.length}
      />
      {!collapsed && (
        <>
          {mode === 'inline' && unmatchedAnnotations.length > 0 && (
            <div className="border-b border-[var(--border)] px-4 py-2 bg-[var(--warning-bg)]">
              <p className="text-xs text-[var(--warning-text)] mb-1">
                Annotations outside visible hunks:
              </p>
              {unmatchedAnnotations.map((ann) => (
                <AnnotationWidget key={ann.id} annotation={ann} />
              ))}
            </div>
          )}
          <div
            className="relative"
            ref={containerRef}
            style={mode === 'side' && sideResult.minHeight > 0 ? { minHeight: sideResult.minHeight } : undefined}
            onMouseOver={handleMouseOver}
            onMouseLeave={handleMouseLeave}
          >
            <div className={mode === 'side' ? 'pr-[380px]' : ''}>
              <div className="text-sm">
                <Diff
                  viewType="unified"
                  diffType={diffData.type}
                  hunks={renderingHunks}
                  widgets={{ ...widgets, ...spacerWidgets }}
                  generateAnchorID={(change) => getChangeKey(change)}
                >
                  {renderHunksWithExpanders}
                </Diff>
              </div>
            </div>
            {mode === 'side' && sideResult.positions.length > 0 && (
              <div className="absolute top-0 right-0 w-[360px]">
                {sideResult.positions.map(({ annotation, top }) => (
                  <SideAnnotation
                    key={annotation.id}
                    annotation={annotation}
                    top={top}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
