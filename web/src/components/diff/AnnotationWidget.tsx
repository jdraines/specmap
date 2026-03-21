import type { Annotation } from '../../api/types';
import { SpecBadge } from './SpecBadge';

interface AnnotationWidgetProps {
  annotation: Annotation;
}

// Matches [N] citation patterns in the description text.
const CITATION_RE = /\[(\d+)\]/g;

export function AnnotationWidget({ annotation }: AnnotationWidgetProps) {
  // Split the description into text segments and citation badges.
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  for (const match of annotation.description.matchAll(CITATION_RE)) {
    const refId = parseInt(match[1], 10);
    const ref = annotation.refs.find((r) => r.id === refId);

    if (match.index > lastIndex) {
      parts.push(annotation.description.slice(lastIndex, match.index));
    }

    if (ref) {
      parts.push(<SpecBadge key={`${annotation.id}-ref-${refId}`} refId={refId} specRef={ref} />);
    } else {
      parts.push(match[0]);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < annotation.description.length) {
    parts.push(annotation.description.slice(lastIndex));
  }

  return (
    <div className="mx-4 my-2 p-3 bg-blue-50 border border-blue-200 rounded-md text-sm">
      <div className="text-xs text-gray-400 font-mono mb-1">
        L{annotation.start_line}-{annotation.end_line}
      </div>
      <div className="text-gray-800 leading-relaxed">{parts}</div>
    </div>
  );
}
