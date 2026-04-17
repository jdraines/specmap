import type { CommentThread as CommentThreadType } from '../../api/types';
import { CommentThread } from './CommentThread';

interface InlineCommentWidgetProps {
  thread: CommentThreadType;
  fullName: string;
  prNumber: number;
}

export function InlineCommentWidget({ thread, fullName, prNumber }: InlineCommentWidgetProps) {
  return (
    <div className="p-3 bg-[var(--comment-bg)] border-l-2 border-[var(--comment-border)]">
      <CommentThread thread={thread} fullName={fullName} prNumber={prNumber} />
    </div>
  );
}
