import { useState, useEffect, useRef, useCallback, type RefObject } from 'react';
import { getChangeKey } from 'react-diff-view';
import type { HunkData, ChangeData } from 'react-diff-view';
import type { Annotation } from '../api/types';

export interface PositionedAnnotation {
  annotation: Annotation;
  top: number;
}

export interface AnnotationPositionsResult {
  positions: PositionedAnnotation[];
  minHeight: number;
  measuredHeightsRef: RefObject<Map<string, number>>;
  heightsVersion: number;
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

const EMPTY_POSITIONS: { positions: PositionedAnnotation[]; minHeight: number } = { positions: [], minHeight: 0 };

export function useAnnotationPositions(
  annotations: Annotation[],
  hunks: HunkData[],
  mode: 'inline' | 'side',
  containerRef: RefObject<HTMLDivElement | null>,
): AnnotationPositionsResult {
  const [result, setResult] = useState(EMPTY_POSITIONS);
  const measuredHeightsRef = useRef<Map<string, number>>(new Map());
  const [heightsVersion, setHeightsVersion] = useState(0);

  const calculate = useCallback(() => {
    const container = containerRef.current;
    if (!container || mode !== 'side' || annotations.length === 0) {
      setResult(EMPTY_POSITIONS);
      return;
    }

    const containerRect = container.getBoundingClientRect();
    const positions: PositionedAnnotation[] = [];

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

      positions.push({ annotation: ann, top });
    }

    positions.sort((a, b) => a.top - b.top);

    // Measure actual rendered heights from DOM
    let heightsChanged = false;
    for (const pos of positions) {
      const el = container.querySelector(`[data-annotation-id="${CSS.escape(pos.annotation.id)}"]`);
      if (el) {
        const h = el.getBoundingClientRect().height;
        const prev = measuredHeightsRef.current.get(pos.annotation.id);
        if (prev === undefined || Math.abs(prev - h) > 1) {
          measuredHeightsRef.current.set(pos.annotation.id, h);
          heightsChanged = true;
        }
      }
    }

    // Only bump version when heights actually changed
    if (heightsChanged) {
      setHeightsVersion((v) => v + 1);
    }

    // Compute minHeight
    let minHeight = 0;
    if (positions.length > 0) {
      const last = positions[positions.length - 1];
      const lastHeight = measuredHeightsRef.current.get(last.annotation.id) ?? 80;
      minHeight = last.top + lastHeight + GAP;
    }

    setResult({ positions, minHeight });
  }, [annotations, hunks, mode, containerRef]);

  useEffect(() => {
    if (mode !== 'side' || annotations.length === 0 || !containerRef.current) {
      setResult(EMPTY_POSITIONS);
      return;
    }

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
  }, [annotations, hunks, mode, containerRef, calculate]);

  return { ...result, measuredHeightsRef, heightsVersion };
}
