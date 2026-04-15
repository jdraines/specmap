import { useEffect, useMemo } from 'react';
import { useParams } from 'react-router';
import type { Annotation } from '../api/types';
import { useReviewStore } from '../stores/reviewStore';
import { useSpecPanelStore } from '../stores/specPanelStore';
import { useLayoutStore } from '../stores/layoutStore';
import { useThemeStore } from '../stores/themeStore';
import { useWalkthroughStore } from '../stores/walkthroughStore';
import { useKeyboardNav } from '../hooks/useKeyboardNav';
import { Breadcrumb } from '../components/ui/Breadcrumb';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { DiffViewer } from '../components/diff/DiffViewer';
import { SpecPanel } from '../components/spec/SpecPanel';
import { ReviewToolbar } from '../components/review/ReviewToolbar';
import { AnnotationNav } from '../components/review/AnnotationNav';
import { GenerateAnnotationsBanner } from '../components/review/GenerateAnnotationsBanner';
import { WalkthroughBanner } from '../components/walkthrough/WalkthroughBanner';
import { WalkthroughNav } from '../components/walkthrough/WalkthroughNav';

function KeyboardHelpOverlay({ onClose, walkthroughActive }: { onClose: () => void; walkthroughActive: boolean }) {
  const shortcuts = [
    ['j / k', 'next / prev file'],
    ['n / p', 'next / prev annotation'],
    ['o', 'toggle file collapse'],
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
          <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] bg-transparent border-0 cursor-pointer text-sm">
            [x]
          </button>
        </div>
        <div className="space-y-2 text-xs">
          {shortcuts.map(([key, desc]) => (
            <div key={key} className="flex justify-between">
              <kbd className="px-1.5 py-0.5 bg-[var(--kbd-bg)] border border-[var(--kbd-border)] text-[var(--text-secondary)]">
                {key}
              </kbd>
              <span className="text-[var(--text-muted)]">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export function PRReviewPage() {
  const { owner, repo, number } = useParams<{
    owner: string;
    repo: string;
    number: string;
  }>();
  const { pr, files, annotationsByFile, loading, error, fetchReview, checkCanGenerate } = useReviewStore();
  const setContext = useSpecPanelStore((s) => s.setContext);
  const closeModal = useSpecPanelStore((s) => s.closeModal);
  const resolvedMode = useLayoutStore((s) => s.resolvedMode);
  const cycleTheme = useThemeStore((s) => s.cycle);
  const walkthroughActive = useWalkthroughStore((s) => s.active);
  const walkthroughData = useWalkthroughStore((s) => s.walkthrough);
  const walkthroughStep = useWalkthroughStore((s) => s.currentStep);
  const checkAvailable = useWalkthroughStore((s) => s.checkAvailable);
  const walkthroughExit = useWalkthroughStore((s) => s.exit);
  const walkthroughNextStep = useWalkthroughStore((s) => s.nextStep);
  const walkthroughPrevStep = useWalkthroughStore((s) => s.prevStep);

  const prNumber = Number(number);

  const allAnnotations = useMemo(() => {
    const result: Annotation[] = [];
    annotationsByFile.forEach((anns) => result.push(...anns));
    return result;
  }, [annotationsByFile]);

  useEffect(() => {
    if (!owner || !repo || !number) return;
    fetchReview(owner, repo, prNumber);
    setContext(owner, repo, prNumber);
    checkAvailable();
    checkCanGenerate();
  }, [owner, repo, number, prNumber, fetchReview, setContext, checkAvailable, checkCanGenerate]);

  const currentWalkthroughStep = walkthroughActive && walkthroughData
    ? walkthroughData.steps[walkthroughStep] ?? null
    : null;

  // Scroll to walkthrough step card when step changes
  useEffect(() => {
    if (!walkthroughActive || !currentWalkthroughStep) return;
    const stepNum = currentWalkthroughStep.step_number;
    const el = document.querySelector(`[data-walkthrough-step="${stepNum}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [walkthroughActive, currentWalkthroughStep]);

  const { showHelp, setShowHelp } = useKeyboardNav({
    fileCount: files.length,
    annotationCount: allAnnotations.length,
    onToggleTheme: cycleTheme,
    onCloseModal: closeModal,
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
          { label: `${owner}/${repo}`, to: `/${owner}/${repo}` },
          { label: `#${pr.number}` },
        ]}
      />
      <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">{pr.title}</h1>
      <p className="text-xs text-[var(--text-secondary)] mb-4">
        {pr.author_login} &middot; {pr.head_branch} &rarr; {pr.base_branch} &middot;{' '}
        <span className="text-[var(--text-muted)]">{pr.head_sha.slice(0, 7)}</span>
      </p>
      <ReviewToolbar annotations={allAnnotations} files={files} annotationsByFile={annotationsByFile} />
      {owner && repo && (
        <GenerateAnnotationsBanner
          owner={owner}
          repo={repo}
          prNumber={prNumber}
          hasAnnotations={allAnnotations.length > 0}
        />
      )}
      {owner && repo && (
        <WalkthroughBanner
          owner={owner}
          repo={repo}
          prNumber={prNumber}
          hasAnnotations={allAnnotations.length > 0}
        />
      )}
      <DiffViewer
        files={files}
        annotationsByFile={annotationsByFile}
        mode={resolvedMode}
        walkthroughStep={currentWalkthroughStep}
        walkthroughTotalSteps={walkthroughData?.steps.length ?? 0}
      />
      <SpecPanel />
      <AnnotationNav annotations={allAnnotations} />
      <WalkthroughNav />
      {showHelp && <KeyboardHelpOverlay onClose={() => setShowHelp(false)} walkthroughActive={walkthroughActive} />}
    </div>
  );
}
