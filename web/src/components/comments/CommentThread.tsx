import { useState, useCallback } from 'react';
import type { CommentThread as CommentThreadType, PostCommentRequest } from '../../api/types';
import { useCommentStore } from '../../stores/commentStore';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function ReactionPills({ reactions }: { reactions: { emoji: string; count: number }[] }) {
  if (!reactions.length) return null;
  const emojiMap: Record<string, string> = {
    '+1': '\ud83d\udc4d', '-1': '\ud83d\udc4e', laugh: '\ud83d\ude04', hooray: '\ud83c\udf89',
    confused: '\ud83d\ude15', heart: '\u2764\ufe0f', rocket: '\ud83d\ude80', eyes: '\ud83d\udc40',
  };
  return (
    <div className="flex gap-1 mt-1">
      {reactions.map((r) => (
        <span
          key={r.emoji}
          className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text-secondary)]"
        >
          {emojiMap[r.emoji] ?? r.emoji} {r.count}
        </span>
      ))}
    </div>
  );
}

interface CommentThreadProps {
  thread: CommentThreadType;
  fullName: string;
  prNumber: number;
}

export function CommentThread({ thread, fullName, prNumber }: CommentThreadProps) {
  const [expanded, setExpanded] = useState(thread.comments.length <= 3);
  const conflict = useCommentStore((s) => s.conflicts.get(thread.thread_id));
  const clearConflict = useCommentStore((s) => s.clearConflict);
  const submitting = useCommentStore((s) => s.submitting);
  const postComment = useCommentStore((s) => s.postComment);
  const drafts = useCommentStore((s) => s.drafts);
  const setDraft = useCommentStore((s) => s.setDraft);

  const draftKey = thread.thread_id;
  const draftText = drafts.get(draftKey) ?? '';

  const visibleComments = expanded
    ? thread.comments
    : thread.comments.length > 3
      ? [thread.comments[0], thread.comments[thread.comments.length - 1]]
      : thread.comments;

  const hiddenCount = thread.comments.length - visibleComments.length;

  const handleSubmit = useCallback(async () => {
    if (!draftText.trim()) return;
    const req: PostCommentRequest = {
      body: draftText,
      thread_id: thread.thread_id,
    };
    await postComment(fullName, prNumber, req);
  }, [draftText, thread.thread_id, postComment, fullName, prNumber]);

  return (
    <div className={`text-sm ${thread.is_resolved ? 'opacity-60' : ''}`}>
      {thread.is_resolved && (
        <div className="text-xs text-[var(--text-muted)] mb-1">(resolved)</div>
      )}
      {thread.is_outdated && (
        <div className="text-xs text-[var(--warning-text)] mb-1">(outdated)</div>
      )}

      {conflict && (
        <div className="mb-2 p-2 bg-[var(--warning-bg)] border border-[var(--warning-text)] text-xs">
          <p className="text-[var(--warning-text)] font-semibold mb-1">
            Thread changed since last refresh
          </p>
          <p className="text-[var(--text-secondary)] mb-1">
            {conflict.fresh.comment_count - conflict.stale.comment_count} new comment(s). Review before resubmitting.
          </p>
          <button
            onClick={() => clearConflict(thread.thread_id)}
            className="text-[var(--accent-text)] hover:underline cursor-pointer bg-transparent border-0 p-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {!expanded && hiddenCount > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className="text-xs text-[var(--accent-text)] hover:underline cursor-pointer bg-transparent border-0 p-0 mb-1"
        >
          {hiddenCount} more {hiddenCount === 1 ? 'reply' : 'replies'}
        </button>
      )}

      <div className="space-y-2">
        {visibleComments.map((comment) => (
          <div key={comment.id} className="flex gap-2">
            {comment.author_avatar && (
              <img
                src={comment.author_avatar}
                alt={comment.author_login}
                className="w-4 h-4 mt-0.5 flex-shrink-0"
              />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-xs">
                <span className="font-medium text-[var(--text-primary)]">{comment.author_login}</span>
                <span className="text-[var(--text-muted)]">{timeAgo(comment.created_at)}</span>
              </div>
              <div className="text-[var(--text-secondary)] mt-0.5 whitespace-pre-wrap break-words">
                {comment.body}
              </div>
              <ReactionPills reactions={comment.reactions} />
            </div>
          </div>
        ))}
      </div>

      {/* Reply form */}
      <div className="mt-2 flex gap-2">
        <textarea
          value={draftText}
          onChange={(e) => setDraft(draftKey, e.target.value)}
          placeholder="Reply..."
          className="flex-1 text-xs p-1.5 bg-[var(--surface-0)] border border-[var(--border)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] resize-none focus:outline-none focus:border-[var(--focus-ring)]"
          rows={1}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={submitting || !draftText.trim()}
          className="text-xs px-2 py-1 bg-[var(--accent)] text-white border-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
        >
          {submitting ? '...' : 'Reply'}
        </button>
      </div>
    </div>
  );
}
