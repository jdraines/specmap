import { useState, useCallback, useRef, useEffect } from 'react';
import type { PostCommentRequest } from '../../api/types';
import { useCommentStore } from '../../stores/commentStore';

interface NewCommentFormProps {
  fullName: string;
  prNumber: number;
  path: string;
  line: number;
  onClose: () => void;
}

export function NewCommentForm({ fullName, prNumber, path, line, onClose }: NewCommentFormProps) {
  const postComment = useCommentStore((s) => s.postComment);
  const submitting = useCommentStore((s) => s.submitting);
  const drafts = useCommentStore((s) => s.drafts);
  const setDraft = useCommentStore((s) => s.setDraft);

  const draftKey = `new:${path}:${line}`;
  const draftText = drafts.get(draftKey) ?? '';
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!draftText.trim()) return;
    const req: PostCommentRequest = {
      body: draftText,
      path,
      line,
    };
    const ok = await postComment(fullName, prNumber, req);
    if (ok) onClose();
  }, [draftText, path, line, postComment, fullName, prNumber, onClose]);

  if (!mounted) return null;

  return (
    <div className="p-3 bg-[var(--comment-bg)] border-l-2 border-[var(--comment-border)]">
      <div className="text-xs text-[var(--text-muted)] mb-1">
        New comment on L{line}
      </div>
      <textarea
        ref={textareaRef}
        value={draftText}
        onChange={(e) => setDraft(draftKey, e.target.value)}
        placeholder="Leave a comment..."
        className="w-full text-xs p-1.5 bg-[var(--surface-0)] border border-[var(--border)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] resize-none focus:outline-none focus:border-[var(--focus-ring)]"
        rows={3}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            handleSubmit();
          }
          if (e.key === 'Escape') {
            onClose();
          }
        }}
      />
      <div className="flex gap-2 mt-1">
        <button
          onClick={handleSubmit}
          disabled={submitting || !draftText.trim()}
          className="text-xs px-2 py-1 bg-[var(--accent)] text-white border-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
        >
          {submitting ? '...' : 'Comment'}
        </button>
        <button
          onClick={onClose}
          className="text-xs px-2 py-1 bg-transparent border border-[var(--border)] text-[var(--text-secondary)] cursor-pointer hover:bg-[var(--hover-bg)]"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
