import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { WalkthroughStep } from '../../api/types';
import { useWalkthroughStore } from '../../stores/walkthroughStore';

interface StepChatProps {
  step: WalkthroughStep;
  fullName: string;
  prNumber: number;
}

export function StepChat({ step, fullName, prNumber }: StepChatProps) {
  const {
    chatExpanded,
    chatStreaming,
    chatStreamContent,
    chatToolCalls,
    chatError,
    toggleChat,
    sendMessage,
  } = useWalkthroughStore();

  const [draft, setDraft] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const expanded = chatExpanded[step.step_number] ?? false;
  const isStreaming = chatStreaming === step.step_number;
  const messages = step.chat ?? [];
  const hasMessages = messages.length > 0;

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = el.scrollHeight + 'px';
    }
  }, [draft]);

  const handleSubmit = useCallback(() => {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft('');
    sendMessage(fullName, prNumber, step.step_number, text);
  }, [draft, isStreaming, fullName, prNumber, step.step_number, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <div className="mt-3 border-t border-[var(--border)] pt-3">
      {/* Toggle button */}
      <button
        onClick={() => toggleChat(step.step_number)}
        className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] bg-transparent border-0 cursor-pointer mb-2"
      >
        {expanded || hasMessages ? (expanded ? 'Collapse chat' : 'Expand chat') : 'Chat about this'}
        <span className="ml-1">{expanded ? '\u25B2' : '\u25BC'}</span>
      </button>

      {expanded && (
        <div>
          {/* Chat messages */}
          {hasMessages && (
            <div className="space-y-3 mb-3">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`text-sm rounded px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-[var(--surface-2)] text-[var(--text-primary)] ml-12'
                      : 'bg-[var(--surface-1)] text-[var(--text-primary)] border border-[var(--border)]'
                  }`}
                >
                  <div className="text-[10px] text-[var(--text-muted)] mb-2 font-medium uppercase tracking-wide">
                    {msg.role === 'user' ? 'You' : 'Assistant'}
                  </div>
                  {msg.role === 'assistant' ? (
                    <div className="themed-prose text-sm">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  )}
                </div>
              ))}

              {/* Streaming response */}
              {isStreaming && (
                <div className="text-sm rounded px-4 py-3 bg-[var(--surface-1)] text-[var(--text-primary)] border border-[var(--border)]">
                  <div className="text-[10px] text-[var(--text-muted)] mb-2 font-medium uppercase tracking-wide">
                    Assistant
                  </div>
                  {/* Tool call indicators */}
                  {chatToolCalls.length > 0 && (
                    <div className="mb-2 space-y-1">
                      {chatToolCalls.map((tc, i) => (
                        <div
                          key={i}
                          className="text-[11px] text-[var(--text-muted)] italic"
                        >
                          {tc.result ? (
                            <details className="cursor-pointer">
                              <summary>Used {tc.tool}</summary>
                              <div className="mt-1 text-[10px] whitespace-pre-wrap opacity-70">
                                {tc.result}
                              </div>
                            </details>
                          ) : (
                            <span>Calling {tc.tool}...</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {chatStreamContent ? (
                    <div className="themed-prose text-sm">
                      <ReactMarkdown>{chatStreamContent}</ReactMarkdown>
                      <span className="inline-block w-1.5 h-4 bg-[var(--text-muted)] animate-pulse ml-0.5 align-text-bottom" />
                    </div>
                  ) : chatToolCalls.length === 0 ? (
                    <span className="inline-block w-1.5 h-4 bg-[var(--text-muted)] animate-pulse" />
                  ) : null}
                </div>
              )}

              {/* Error */}
              {chatError && (
                <div className="text-xs text-[var(--error-text)] px-3 py-2">
                  {chatError}
                </div>
              )}

            </div>
          )}

          {/* Input area */}
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about this step..."
              disabled={isStreaming}
              rows={1}
              className="flex-1 resize-none overflow-hidden text-sm px-3 py-2 border border-[var(--border)] bg-[var(--surface-0)] text-[var(--text-primary)] rounded placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--focus-ring)] disabled:opacity-50"
              style={{ maxHeight: '120px' }}
            />
            <button
              onClick={handleSubmit}
              disabled={isStreaming || !draft.trim()}
              className="px-3 py-2 text-xs font-medium bg-[var(--accent)] text-white border-0 rounded cursor-pointer hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
