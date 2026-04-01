import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';

interface SpecContentProps {
  content: string;
  heading: string;
}

function extractSection(markdown: string, heading: string): string {
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

  if (startIdx === -1) return markdown;

  let endIdx = lines.length;
  for (let i = startIdx + 1; i < lines.length; i++) {
    const match = lines[i].match(/^(#{1,6})\s/);
    if (match && match[1].length <= startLevel) {
      endIdx = i;
      break;
    }
  }

  return lines.slice(startIdx, endIdx).join('\n');
}

export function SpecContent({ content, heading }: SpecContentProps) {
  const section = useMemo(() => extractSection(content, heading), [content, heading]);

  return (
    <div className="themed-prose prose prose-sm max-w-none">
      <ReactMarkdown>{section}</ReactMarkdown>
    </div>
  );
}
