import { useEffect, useMemo } from 'react';
import type { Annotation } from '../api/types';
import { useReviewStore } from '../stores/reviewStore';
import { useSpecPanelStore } from '../stores/specPanelStore';
import { useLayoutStore } from '../stores/layoutStore';
import { useThemeStore } from '../stores/themeStore';
import { useWalkthroughStore } from '../stores/walkthroughStore';
import { useCodeReviewStore } from '../stores/codeReviewStore';
import { useCommentStore } from '../stores/commentStore';
import { useKeyboardNav } from '../hooks/useKeyboardNav';
import { Breadcrumb } from '../components/ui/Breadcrumb';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { DiffViewer } from '../components/diff/DiffViewer';
import { SpecPanel } from '../components/spec/SpecPanel';
import { ReviewToolbar } from '../components/review/ReviewToolbar';
import { AnnotationNav } from '../components/review/AnnotationNav';
import { GenerateAnnotationsBanner } from '../components/review/GenerateAnnotationsBanner';
import { ConversationPanel } from '../components/comments/ConversationPanel';
import { FileTree } from '../components/filetree/FileTree';
import { WalkthroughBanner } from '../components/walkthrough/WalkthroughBanner';
import { WalkthroughNav } from '../components/walkthrough/WalkthroughNav';
import { CodeReviewBanner } from '../components/codereview/CodeReviewBanner';
import { CodeReviewNav } from '../components/codereview/CodeReviewNav';

function KeyboardHelpOverlay({ onClose, walkthroughActive }: { onClose: () => void; walkthroughActive: boolean }) {
  const shortcuts = [
    ['j / k', 'next / prev file'],
    ['n / p', 'next / prev annotation'],
    ['o', 'toggle file collapse'],
    ['b', 'toggle file tree'],
    ['t', 'cycle theme'],
    ['?', 'toggle this help'],
    ['Esc', 'close modal / help'],
  ];

  if (walkthroughActive) {
    shortcuts.push(
      ['] / \u2192', 'next walkthrough step'],
      ['[ / \u2190', 'prev walkthrough step'],
    );
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-[9998]" onClick={onClose} />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[9999] bg-[var(--surface-1)] border border-[var(--border)] shadow-xl p-6 w-80">
        <div className="flex justify-between items-center mb-4">
          <span className="text-sm font-semibold text-[var(--text-primary)]">keyboard shortcuts</span>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] bg-transparent border-0 cursor-pointer text-sm">
            [x]
          </button>
        </div>
        <div className="space-y-2 text-xs">
          {shortcuts.map(([key, desc]) => (
            <div key={key} className="flex justify-between">
              <kbd className="px-1.5 py-0.5 bg-[var(--kbd-bg)] border border-[var(--kbd-border)] text-[var(--text-secondary)]">
                {key}
              </kbd>
              <span className="text-[var(--text-secondary)]">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

interface PRReviewPageProps {
  fullName: string;
  prNumber: number;
}

export function PRReviewPage({ fullName, prNumber }: PRReviewPageProps) {
  const { pr, files, annotationsByFile, loading, error, fetchReview, checkCanGenerate } = useReviewStore();
  const setContext = useSpecPanelStore((s) => s.setContext);
  const closeModal = useSpecPanelStore((s) => s.closeModal);
  const preloadSpecs = useSpecPanelStore((s) => s.preloadSpecs);
  const resolvedMode = useLayoutStore((s) => s.resolvedMode);
  const fileTreeOpen = useLayoutStore((s) => s.fileTreeOpen);
  const toggleFileTree = useLayoutStore((s) => s.toggleFileTree);
  const cycleTheme = useThemeStore((s) => s.cycle);
  const walkthroughActive = useWalkthroughStore((s) => s.active);
  const walkthroughData = useWalkthroughStore((s) => s.walkthrough);
  const walkthroughStep = useWalkthroughStore((s) => s.currentStep);
  const checkWalkthroughAvailable = useWalkthroughStore((s) => s.checkAvailable);
  const walkthroughExit = useWalkthroughStore((s) => s.exit);
  const walkthroughNextStep = useWalkthroughStore((s) => s.nextStep);
  const walkthroughPrevStep = useWalkthroughStore((s) => s.prevStep);
  const codeReviewActive = useCodeReviewStore((s) => s.active);
  const codeReviewData = useCodeReviewStore((s) => s.review);
  const codeReviewIssueIdx = useCodeReviewStore((s) => s.currentIssue);
  const checkCodeReviewAvailable = useCodeReviewStore((s) => s.checkAvailable);
  const fetchComments = useCommentStore((s) => s.fetchComments);
  const startPolling = useCommentStore((s) => s.startPolling);
  const stopPolling = useCommentStore((s) => s.stopPolling);
  const threadsByFile = useCommentStore((s) => s.threadsByFile);

  const allAnnotations = useMemo(() => {
    const result: Annotation[] = [];
    annotationsByFile.forEach((anns) => result.push(...anns));
    return result;
  }, [annotationsByFile]);

  const commentCountByFile = useMemo(() => {
    const counts = new Map<string, number>();
    threadsByFile.forEach((threads, file) => {
      counts.set(file, threads.length);
    });
    return counts;
  }, [threadsByFile]);

  useEffect(() => {
    if (!fullName) return;
    fetchReview(fullName, prNumber);
    setContext(fullName, prNumber);
    checkWalkthroughAvailable();
    checkCodeReviewAvailable();
    checkCanGenerate();
    fetchComments(fullName, prNumber);
    startPolling(fullName, prNumber);
    return () => stopPolling();
  }, [fullName, prNumber, fetchReview, setContext, checkWalkthroughAvailable, checkCodeReviewAvailable, checkCanGenerate, fetchComments, startPolling, stopPolling]);

  // Preload spec files referenced by annotations and walkthrough
  useEffect(() => {
    if (allAnnotations.length > 0) {
      preloadSpecs(allAnnotations, walkthroughData?.steps);
    }
  }, [allAnnotations, walkthroughData, preloadSpecs]);

  // Mutual exclusion: if both become active, exit the other
  useEffect(() => {
    if (walkthroughActive && codeReviewActive) {
      // Walkthrough just became active, exit code review
      useCodeReviewStore.getState().exit();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [walkthroughActive]);

  useEffect(() => {
    if (codeReviewActive && walkthroughActive) {
      // Code review just became active, exit walkthrough
      useWalkthroughStore.getState().exit();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codeReviewActive]);

  const currentWalkthroughStep = walkthroughActive && walkthroughData
    ? walkthroughData.steps[walkthroughStep] ?? null
    : null;

  const currentCodeReviewIssue = codeReviewActive && codeReviewData
    ? codeReviewData.issues[codeReviewIssueIdx] ?? null
    : null;

  // Scroll to walkthrough step card when navigating to a different step
  // Use step_number (primitive) not the step object to avoid re-scrolling on chat updates
  const currentStepNumber = currentWalkthroughStep?.step_number ?? null;
  useEffect(() => {
    if (!walkthroughActive || currentStepNumber == null) return;
    const el = document.querySelector(`[data-walkthrough-step="${currentStepNumber}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [walkthroughActive, currentStepNumber]);

  // Scroll to code review issue card when navigating to a different issue
  const currentIssueNumber = currentCodeReviewIssue?.issue_number ?? null;
  useEffect(() => {
    if (!codeReviewActive || currentIssueNumber == null) return;
    const el = document.querySelector(`[data-code-review-issue="${currentIssueNumber}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [codeReviewActive, currentIssueNumber]);

  const { showHelp, setShowHelp } = useKeyboardNav({
    fileCount: files.length,
    annotationCount: allAnnotations.length,
    onToggleTheme: cycleTheme,
    onCloseModal: closeModal,
    onToggleFileTree: toggleFileTree,
    walkthroughActive,
    onWalkthroughNext: walkthroughNextStep,
    onWalkthroughPrev: walkthroughPrevStep,
    onWalkthroughExit: walkthroughExit,
  });

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-[var(--error-text)]">{error}</p>;
  if (!pr) return null;

  return (
    <div>
      <Breadcrumb
        items={[
          { label: 'repos', to: '/' },
          { label: fullName, to: `/r/${fullName}` },
          { label: `#${pr.number}` },
        ]}
      />
      <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">{pr.title}</h1>
      <p className="text-xs text-[var(--text-secondary)] mb-4">
        {pr.author_login} &middot; {pr.head_branch} &rarr; {pr.base_branch} &middot;{' '}
        <span className="text-[var(--text-secondary)]">{pr.head_sha.slice(0, 7)}</span>
        {files.length > 0 && (() => {
          const adds = files.reduce((s, f) => s + f.additions, 0);
          const dels = files.reduce((s, f) => s + f.deletions, 0);
          return (
            <>
              {' '}&middot;{' '}
              <span className="text-[var(--insert-text)]">+{adds}</span>
              {' '}
              <span className="text-[var(--delete-text)]">-{dels}</span>
              {' '}
              <span className="text-[var(--text-secondary)]">({adds + dels} lines across {files.length} files)</span>
            </>
          );
        })()}
      </p>
      <ReviewToolbar annotations={allAnnotations} files={files} annotationsByFile={annotationsByFile} />
      <div className="flex gap-4">
        {fileTreeOpen && (
          <div className="w-[240px] flex-shrink-0 sticky top-0 self-start bg-[var(--surface-1)] border border-[var(--border)]">
            <FileTree
              files={files}
              annotationsByFile={annotationsByFile}
              commentCountByFile={commentCountByFile}
            />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <GenerateAnnotationsBanner
            fullName={fullName}
            prNumber={prNumber}
            hasAnnotations={allAnnotations.length > 0}
          />
          <CodeReviewBanner
            fullName={fullName}
            prNumber={prNumber}
          />
          <WalkthroughBanner
            fullName={fullName}
            prNumber={prNumber}
            hasAnnotations={allAnnotations.length > 0}
          />
          <ConversationPanel fullName={fullName} prNumber={prNumber} />
          <DiffViewer
            files={files}
            annotationsByFile={annotationsByFile}
            mode={resolvedMode}
            walkthroughStep={currentWalkthroughStep}
            walkthroughTotalSteps={walkthroughData?.steps.length ?? 0}
            codeReviewIssue={currentCodeReviewIssue}
            codeReviewTotalIssues={codeReviewData?.issues.length ?? 0}
            fullName={fullName}
            prNumber={prNumber}
          />
        </div>
      </div>
      <SpecPanel />
      <AnnotationNav annotations={allAnnotations} />
      <WalkthroughNav />
      <CodeReviewNav />
      {showHelp && <KeyboardHelpOverlay onClose={() => setShowHelp(false)} walkthroughActive={walkthroughActive} />}
    </div>
  );
}
