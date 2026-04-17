import { useState, useCallback } from 'react';
import type { PostCommentRequest } from '../../api/types';
import { useCommentStore } from '../../stores/commentStore';
import { CommentThread } from './CommentThread';

interface ConversationPanelProps {
  fullName: string;
  prNumber: number;
}

export function ConversationPanel({ fullName, prNumber }: ConversationPanelProps) {
  const generalComments = useCommentStore((s) => s.generalComments);
  const postComment = useCommentStore((s) => s.postComment);
  const submitting = useCommentStore((s) => s.submitting);
  const [collapsed, setCollapsed] = useState(false);
  const [newBody, setNewBody] = useState('');

  const handlePost = useCallback(async () => {
    if (!newBody.trim()) return;
    const req: PostCommentRequest = { body: newBody };
    const ok = await postComment(fullName, prNumber, req);
    if (ok) setNewBody('');
  }, [newBody, postComment, fullName, prNumber]);

  if (generalComments.length === 0) return null;

  return (
    <div className="mb-4 bg-[var(--surface-1)] border border-[var(--border)]">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-4 py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--hover-bg)] cursor-pointer bg-transparent border-0 text-left"
      >
        <span className="w-3">{collapsed ? '+' : '-'}</span>
        <span>Conversation ({generalComments.length})</span>
      </button>
      {!collapsed && (
        <div className="px-4 pb-3 space-y-3">
          {generalComments.map((thread) => (
            <div key={thread.thread_id} className="border-b border-[var(--border)] pb-3 last:border-0 last:pb-0">
              <CommentThread thread={thread} fullName={fullName} prNumber={prNumber} />
            </div>
          ))}
          {/* New general comment form */}
          <div className="pt-2 border-t border-[var(--border)]">
            <textarea
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              placeholder="Leave a comment..."
              className="w-full text-xs p-1.5 bg-[var(--surface-0)] border border-[var(--border)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] resize-none focus:outline-none focus:border-[var(--focus-ring)]"
              rows={2}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handlePost();
                }
              }}
            />
            <button
              onClick={handlePost}
              disabled={submitting || !newBody.trim()}
              className="mt-1 text-xs px-2 py-1 bg-[var(--accent)] text-white border-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
            >
              {submitting ? '...' : 'Comment'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
