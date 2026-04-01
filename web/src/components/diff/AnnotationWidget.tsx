import type { Annotation } from '../../api/types';
import { SpecBadge } from './SpecBadge';

const CITATION_RE = /\[(\d+)\]/g;

interface AnnotationContentProps {
  annotation: Annotation;
}

export function AnnotationContent({ annotation }: AnnotationContentProps) {
  // Strip citation markers from text
  const cleanText = annotation.description
    .replace(CITATION_RE, '')
    .replace(/\s{2,}/g, ' ')
    .trim();

  // Collect matching refs
  const refEntries: { id: number; ref: NonNullable<(typeof annotation.refs)[number]> }[] = [];
  for (const match of annotation.description.matchAll(CITATION_RE)) {
    const refId = parseInt(match[1], 10);
    const ref = annotation.refs.find((r) => r.id === refId);
    if (ref) refEntries.push({ id: refId, ref });
  }

  return (
    <>
      <div className="text-[var(--text-primary)] leading-relaxed">{cleanText}</div>
      {refEntries.length > 0 && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          {refEntries.map(({ id, ref }) => (
            <SpecBadge key={id} refId={id} specRef={ref} />
          ))}
        </div>
      )}
    </>
  );
}

interface AnnotationWidgetProps {
  annotation: Annotation;
}

export function AnnotationWidget({ annotation }: AnnotationWidgetProps) {
  return (
    <div
      className="p-3 bg-[var(--annotation-bg)] border-l-2 border-[var(--annotation-border)] text-sm"
      data-annotation-id={annotation.id}
    >
      <div className="text-xs text-[var(--text-muted)] mb-1">
        L{annotation.start_line}-{annotation.end_line}
      </div>
      <AnnotationContent annotation={annotation} />
    </div>
  );
}
