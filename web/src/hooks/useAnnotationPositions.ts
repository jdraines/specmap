import { useState, useEffect, useRef, useCallback, type RefObject } from 'react';
import { getChangeKey } from 'react-diff-view';
import type { HunkData, ChangeData } from 'react-diff-view';
import type { Annotation } from '../api/types';

export interface PositionedAnnotation {
  annotation: Annotation;
  top: number;
  overlapping: boolean;
}

export interface AnnotationPositionsResult {
  positions: PositionedAnnotation[];
  minHeight: number;
}

function findChangeKeyForLine(hunks: HunkData[], line: number): string | null {
  for (const hunk of hunks) {
    for (const change of hunk.changes) {
      const changeLine =
        change.type === 'delete'
          ? (change as ChangeData & { lineNumber: number }).lineNumber
          : change.type === 'insert'
            ? (change as ChangeData & { lineNumber: number }).lineNumber
            : (change as ChangeData & { newLineNumber: number }).newLineNumber;
      if (changeLine === line) return getChangeKey(change);
    }
  }
  return null;
}

const GAP = 8;

const EMPTY: AnnotationPositionsResult = { positions: [], minHeight: 0 };

export function useAnnotationPositions(
  annotations: Annotation[],
  hunks: HunkData[],
  mode: 'inline' | 'side',
  containerRef: RefObject<HTMLDivElement | null>,
  expandedIds: Set<string> = new Set(),
): AnnotationPositionsResult {
  const [result, setResult] = useState<AnnotationPositionsResult>(EMPTY);
  const measuredHeights = useRef<Map<string, number>>(new Map());

  const calculate = useCallback(() => {
    const container = containerRef.current;
    if (!container || mode !== 'side' || annotations.length === 0) {
      setResult(EMPTY);
      return;
    }

    const containerRect = container.getBoundingClientRect();
    const positions: PositionedAnnotation[] = [];

    // First pass: position at natural code-line-aligned positions
    for (const ann of annotations) {
      let key: string | null = null;
      for (let line = ann.start_line; line <= ann.end_line; line++) {
        key = findChangeKeyForLine(hunks, line);
        if (key) break;
      }

      let top = 0;
      if (key) {
        const tr = container.querySelector(`[id="${CSS.escape(key)}"]`);
        if (tr) {
          const trRect = tr.getBoundingClientRect();
          top = trRect.top - containerRect.top;
        }
      }

      positions.push({ annotation: ann, top, overlapping: false });
    }

    // Sort by natural position
    positions.sort((a, b) => a.top - b.top);

    // Measure actual rendered heights from DOM
    for (const pos of positions) {
      const el = container.querySelector(`[data-annotation-id="${CSS.escape(pos.annotation.id)}"]`);
      if (el) {
        measuredHeights.current.set(pos.annotation.id, el.getBoundingClientRect().height);
      }
    }

    // Detect overlaps and adjust expanded annotations
    for (let i = 1; i < positions.length; i++) {
      const prevId = positions[i - 1].annotation.id;
      const prevHeight = measuredHeights.current.get(prevId) ?? 80;
      const prevBottom = positions[i - 1].top + prevHeight;

      if (positions[i].top < prevBottom) {
        positions[i].overlapping = true;
      }

      // If previous annotation is expanded, push this one down
      if (expandedIds.has(prevId)) {
        const minTop = prevBottom + GAP;
        if (positions[i].top < minTop) {
          positions[i].top = minTop;
          // After being pushed down, re-check overlap (it was forced down, so not "naturally" overlapping)
          positions[i].overlapping = false;
        }
      }
    }

    // Compute minHeight
    let minHeight = 0;
    if (positions.length > 0) {
      const last = positions[positions.length - 1];
      const lastHeight = measuredHeights.current.get(last.annotation.id) ?? 80;
      minHeight = last.top + lastHeight + GAP;
    }

    setResult({ positions, minHeight });
  }, [annotations, hunks, mode, containerRef, expandedIds]);

  useEffect(() => {
    if (mode !== 'side' || annotations.length === 0 || !containerRef.current) {
      setResult(EMPTY);
      return;
    }

    // Defer to let layout settle, then calculate twice:
    // first pass positions annotations, second pass measures their actual heights
    const raf = requestAnimationFrame(() => {
      calculate();
      requestAnimationFrame(calculate);
    });

    const observer = new ResizeObserver(calculate);
    if (containerRef.current) observer.observe(containerRef.current);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [annotations, hunks, mode, containerRef, expandedIds, calculate]);

  return result;
}
