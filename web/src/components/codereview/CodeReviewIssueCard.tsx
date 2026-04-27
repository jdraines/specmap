import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { CodeReviewIssue } from '../../api/types';
import { useCodeReviewStore } from '../../stores/codeReviewStore';

interface CodeReviewIssueCardProps {
  issue: CodeReviewIssue;
  totalIssues: number;
  fullName: string;
  prNumber: number;
}

const severityColor: Record<string, string> = {
  P0: 'var(--cr-p0)',
  P1: 'var(--cr-p1)',
  P2: 'var(--cr-p2)',
  P3: 'var(--cr-p3)',
  P4: 'var(--cr-p4)',
};

const categoryLabels: Record<string, string> = {
  correctness: 'Correctness',
  security: 'Security',
  performance: 'Performance',
  style: 'Style',
  design: 'Design',
};

export function CodeReviewIssueCard({ issue, totalIssues, fullName, prNumber }: CodeReviewIssueCardProps) {
  const { nextIssue, prevIssue, exit, currentIssue } = useCodeReviewStore();
  const [showFix, setShowFix] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);

  return (
    <div
      className="font-sans bg-gradient-to-r from-[var(--cr-gradient-from)] to-[var(--cr-gradient-to)] p-4"
      data-code-review-issue={issue.issue_number}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="inline-flex items-center gap-2 text-xs">
          <span
            className="inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[10px] font-bold text-white"
            style={{ backgroundColor: severityColor[issue.severity] || 'var(--cr-border)' }}
          >
            {issue.severity}
          </span>
          <span className="font-medium text-[var(--text-secondary)]">
            Issue {issue.issue_number} of {totalIssues}
          </span>
          {issue.category && (
            <span className="px-1.5 py-0.5 text-[10px] bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-strong)] rounded font-medium">
              {categoryLabels[issue.category] || issue.category}
            </span>
          )}
        </span>
        <button
          onClick={exit}
          className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-secondary)] bg-transparent border-0 cursor-pointer"
        >
          exit review
        </button>
      </div>

      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">{issue.title}</h3>

      <div className="themed-prose text-sm mb-3">
        <ReactMarkdown>{issue.description}</ReactMarkdown>
      </div>

      {issue.suggested_fix && (
        <div className="mb-3">
          <button
            onClick={() => setShowFix(!showFix)}
            className="text-xs text-[var(--accent-text)] hover:underline bg-transparent border-0 cursor-pointer mb-1"
          >
            {showFix ? 'Hide suggested fix' : 'Show suggested fix'} {showFix ? '\u25B2' : '\u25BC'}
          </button>
          {showFix && (
            <div className="themed-prose text-sm border-l-2 border-[var(--cr-border)] pl-3 ml-1">
              <ReactMarkdown>{issue.suggested_fix}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {issue.reasoning && (
        <div className="mb-3">
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            className="text-xs text-[var(--text-secondary)] hover:underline bg-transparent border-0 cursor-pointer mb-1"
          >
            {showReasoning ? 'Hide reasoning' : 'Show reasoning'} {showReasoning ? '\u25B2' : '\u25BC'}
          </button>
          {showReasoning && (
            <div className="themed-prose text-sm border-l-2 border-[var(--border-strong)] pl-3 ml-1">
              <ReactMarkdown>{issue.reasoning}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={prevIssue}
          disabled={currentIssue === 0}
          className="px-2 py-1 text-xs font-medium bg-[var(--surface-1)] text-[var(--text-secondary)] border border-[var(--cr-border)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--cr-border)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <button
          onClick={nextIssue}
          disabled={currentIssue >= totalIssues - 1}
          className="px-2 py-1 text-xs font-medium bg-[var(--surface-1)] text-[var(--text-secondary)] border border-[var(--cr-border)] cursor-pointer hover:bg-[color-mix(in_srgb,var(--cr-border)_15%,transparent)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>

      <IssueChat issue={issue} fullName={fullName} prNumber={prNumber} />
    </div>
  );
}

function IssueChat({ issue, fullName, prNumber }: { issue: CodeReviewIssue; fullName: string; prNumber: number }) {
  const {
    chatExpanded,
    chatStreaming,
    chatStreamContent,
    chatToolCalls,
    chatError,
    toggleChat,
    sendMessage,
  } = useCodeReviewStore();

  // Adapt the issue to look like a WalkthroughStep for StepChat reuse
  // StepChat expects step.step_number, step.chat, and uses walkthroughStore
  // We can't reuse StepChat directly since it's tied to walkthroughStore.
  // Instead, inline a minimal chat UI using the same pattern.

  const expanded = chatExpanded[issue.issue_number] ?? false;
  const isStreaming = chatStreaming === issue.issue_number;
  const messages = issue.chat ?? [];
  const hasMessages = messages.length > 0;

  const [draft, setDraft] = useState('');

  const handleSubmit = () => {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft('');
    sendMessage(fullName, prNumber, issue.issue_number, text);
  };

  return (
    <div className="mt-3 border-t border-[var(--border-strong)] pt-3">
      <button
        onClick={() => toggleChat(issue.issue_number)}
        className="text-xs text-[var(--text-primary)] hover:text-[var(--accent-text)] bg-transparent border-0 cursor-pointer mb-2 font-medium"
      >
        {expanded || hasMessages ? (expanded ? 'Collapse chat' : 'Expand chat') : 'Chat about this'}
        <span className="ml-1">{expanded ? '\u25B2' : '\u25BC'}</span>
      </button>

      {expanded && (
        <div>
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
                  <div className="text-[10px] text-[var(--text-secondary)] mb-2 font-medium uppercase tracking-wide">
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

              {isStreaming && (
                <div className="text-sm rounded px-4 py-3 bg-[var(--surface-1)] text-[var(--text-primary)] border border-[var(--border)]">
                  <div className="text-[10px] text-[var(--text-secondary)] mb-2 font-medium uppercase tracking-wide">
                    Assistant
                  </div>
                  {chatToolCalls.length > 0 && (
                    <div className="mb-2 space-y-1">
                      {chatToolCalls.map((tc, i) => (
                        <div key={i} className="text-[11px] text-[var(--text-secondary)] italic">
                          {tc.result ? (
                            <details className="cursor-pointer">
                              <summary>Used {tc.tool}</summary>
                              <div className="mt-1 text-[10px] whitespace-pre-wrap opacity-70">{tc.result}</div>
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

              {chatError && (
                <div className="text-xs text-[var(--error-text)] px-3 py-2">{chatError}</div>
              )}
            </div>
          )}

          <div className="flex items-end gap-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="Ask about this issue..."
              disabled={isStreaming}
              rows={1}
              className="flex-1 resize-none overflow-hidden text-sm px-3 py-2 border border-[var(--border)] bg-[var(--surface-0)] text-[var(--text-primary)] rounded placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--focus-ring)] disabled:opacity-50"
              style={{ maxHeight: '120px' }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = 'auto';
                el.style.height = el.scrollHeight + 'px';
              }}
            />
            <button
              onClick={handleSubmit}
              disabled={isStreaming || !draft.trim()}
              className="px-3 py-2 text-xs font-medium bg-[var(--cr-border)] text-white border-0 rounded cursor-pointer hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
