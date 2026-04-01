import type { Annotation } from '../../api/types';
import { AnnotationContent } from './AnnotationWidget';

interface SideAnnotationProps {
  annotation: Annotation;
  top: number;
}

export function SideAnnotation({ annotation, top }: SideAnnotationProps) {
  return (
    <div
      className="absolute right-0 w-[360px] transition-[box-shadow,opacity] duration-150"
      style={{ top }}
      data-annotation-id={annotation.id}
    >
      <div className="border-l-2 border-[var(--annotation-border)] bg-[var(--annotation-bg)] p-3 text-sm">
        <div className="text-xs text-[var(--text-muted)] mb-1">
          L{annotation.start_line}-{annotation.end_line}
        </div>
        <AnnotationContent annotation={annotation} />
      </div>
    </div>
  );
}
