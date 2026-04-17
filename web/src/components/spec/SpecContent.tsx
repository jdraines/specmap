import { useMemo, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';

interface SpecContentProps {
  content: string;
  heading: string;
}

function findHeadingRange(markdown: string, heading: string): { start: number; end: number } | null {
  const segments = heading.split('>').map((s) => s.trim());
  const target = segments[segments.length - 1];

  const lines = markdown.split('\n');
  let startIdx = -1;
  let startLevel = 0;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(/^(#{1,6})\s+(.+)/);
    if (match && match[2].trim() === target) {
      startIdx = i;
      startLevel = match[1].length;
      break;
    }
  }

  if (startIdx === -1) return null;

  let endIdx = lines.length;
  for (let i = startIdx + 1; i < lines.length; i++) {
    const match = lines[i].match(/^(#{1,6})\s/);
    if (match && match[1].length <= startLevel) {
      endIdx = i;
      break;
    }
  }

  return { start: startIdx, end: endIdx };
}

export function SpecContent({ content, heading }: SpecContentProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);

  const range = useMemo(() => findHeadingRange(content, heading), [content, heading]);

  // Scroll to the target section after render
  useEffect(() => {
    if (!highlightRef.current) return;
    // Use requestAnimationFrame to wait for layout
    requestAnimationFrame(() => {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }, [content, heading]);

  if (!range) {
    // Heading not found — render full content without highlight
    return (
      <div className="themed-prose prose prose-sm max-w-none">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }

  // Split content into before, target section, and after
  const lines = content.split('\n');
  const before = lines.slice(0, range.start).join('\n');
  const section = lines.slice(range.start, range.end).join('\n');
  const after = lines.slice(range.end).join('\n');

  return (
    <div ref={containerRef} className="themed-prose prose prose-sm max-w-none">
      {before && (
        <div className="opacity-60">
          <ReactMarkdown>{before}</ReactMarkdown>
        </div>
      )}
      <div
        ref={highlightRef}
        className="border-l-2 border-[var(--accent)] pl-3 -ml-3 bg-[var(--spec-highlight-bg)] py-1 scroll-mt-4"
      >
        <ReactMarkdown>{section}</ReactMarkdown>
      </div>
      {after && (
        <div className="opacity-60">
          <ReactMarkdown>{after}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
