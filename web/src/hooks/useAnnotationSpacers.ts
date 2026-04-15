import { useMemo, type RefObject, type ReactNode, createElement } from 'react';
import { getChangeKey } from 'react-diff-view';
import type { HunkData, ChangeData } from 'react-diff-view';
import type { Annotation } from '../api/types';

const GAP = 8;

function getChangeLine(change: ChangeData): number {
  if (change.type === 'delete') return (change as ChangeData & { lineNumber: number }).lineNumber;
  if (change.type === 'insert') return (change as ChangeData & { lineNumber: number }).lineNumber;
  return (change as ChangeData & { newLineNumber: number }).newLineNumber;
}

/**
 * Find the change key for the first visible change line in [startLine, endLine].
 */
function findChangeKeyForLine(hunks: HunkData[], line: number): string | null {
  for (const hunk of hunks) {
    for (const change of hunk.changes) {
      if (getChangeLine(change) === line) return getChangeKey(change);
    }
  }
  return null;
}

/**
 * Find the change key for the last visible change line at or before `line`.
 */
function findNearestChangeKeyAtOrBefore(hunks: HunkData[], line: number): string | null {
  let best: ChangeData | null = null;
  let bestLine = -1;
  for (const hunk of hunks) {
    for (const change of hunk.changes) {
      if (change.type === 'delete') continue;
      const changeLine = getChangeLine(change);
      if (changeLine <= line && changeLine > bestLine) {
        best = change;
        bestLine = changeLine;
      }
    }
  }
  return best ? getChangeKey(best) : null;
}

export function useAnnotationSpacers(
  annotations: Annotation[],
  hunks: HunkData[],
  mode: 'inline' | 'side',
  containerRef: RefObject<HTMLDivElement | null>,
  measuredHeightsRef: RefObject<Map<string, number>>,
  heightsVersion: number,
): Record<string, ReactNode> {
  return useMemo(() => {
    if (mode !== 'side' || annotations.length < 2) return {};

    const container = containerRef.current;
    if (!container) return {};

    // Measure rowHeight from any code line <tr>
    const sampleTr = container.querySelector('tr.diff-line');
    if (!sampleTr) return {};
    const rowHeight = sampleTr.getBoundingClientRect().height;
    if (rowHeight <= 0) return {};

    // Build flat index: changeKey → { index, hunkIdx }
    const changeIndex = new Map<string, { index: number; hunkIdx: number }>();
    let flatIdx = 0;
    for (let hi = 0; hi < hunks.length; hi++) {
      for (const change of hunks[hi].changes) {
        changeIndex.set(getChangeKey(change), { index: flatIdx, hunkIdx: hi });
        flatIdx++;
      }
    }

    // Sort annotations by start_line
    const sorted = [...annotations].sort((a, b) => a.start_line - b.start_line);

    // Find anchor change key for each annotation (first visible change in its line range)
    const anchorKeys: (string | null)[] = sorted.map((ann) => {
      for (let line = ann.start_line; line <= ann.end_line; line++) {
        const key = findChangeKeyForLine(hunks, line);
        if (key) return key;
      }
      return null;
    });

    const spacers: Record<string, ReactNode> = {};
    const measuredHeights = measuredHeightsRef.current;

    for (let i = 1; i < sorted.length; i++) {
      const prev = sorted[i - 1];
      const prevKey = anchorKeys[i - 1];
      const currKey = anchorKeys[i];
      if (!prevKey || !currKey) continue;

      const prevInfo = changeIndex.get(prevKey);
      const currInfo = changeIndex.get(currKey);
      if (!prevInfo || !currInfo) continue;

      // Count change rows between the two anchors
      const changeRowsBetween = currInfo.index - prevInfo.index;

      // Count hunk boundaries between them (each boundary = one decoration row)
      const decorationRows = currInfo.hunkIdx - prevInfo.hunkIdx;

      const naturalDist = (changeRowsBetween + decorationRows) * rowHeight;
      const prevHeight = measuredHeights.get(prev.id) ?? 80;
      const shortfall = prevHeight + GAP - naturalDist;

      if (shortfall <= 0) continue;

      // Place spacer at the change key nearest to prev annotation's end line
      const spacerKey = findNearestChangeKeyAtOrBefore(hunks, prev.end_line);
      if (!spacerKey) continue;

      // If there's already a spacer on this key, take the larger value
      const existingHeight = spacers[spacerKey]
        ? parseFloat((spacers[spacerKey] as any)?.props?.style?.height) || 0
        : 0;

      const spacerHeight = Math.max(shortfall, existingHeight);

      spacers[spacerKey] = createElement('div', {
        className: 'diff-widget-spacer',
        style: { height: spacerHeight },
        'aria-hidden': true,
      });
    }

    return spacers;
  }, [annotations, hunks, mode, containerRef, heightsVersion]);
}
