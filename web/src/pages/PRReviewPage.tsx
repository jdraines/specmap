import { useEffect } from 'react';
import { useParams } from 'react-router';
import { useReviewStore } from '../stores/reviewStore';
import { useSpecPanelStore } from '../stores/specPanelStore';
import { Breadcrumb } from '../components/ui/Breadcrumb';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { DiffViewer } from '../components/diff/DiffViewer';
import { SpecPanel } from '../components/spec/SpecPanel';

export function PRReviewPage() {
  const { owner, repo, number } = useParams<{
    owner: string;
    repo: string;
    number: string;
  }>();
  const { pr, files, annotationsByFile, loading, error, fetchReview } = useReviewStore();
  const setContext = useSpecPanelStore((s) => s.setContext);

  const prNumber = Number(number);

  useEffect(() => {
    if (!owner || !repo || !number) return;
    fetchReview(owner, repo, prNumber);
    setContext(owner, repo, prNumber);
  }, [owner, repo, number, prNumber, fetchReview, setContext]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!pr) return null;

  return (
    <div className="flex">
      <div className="flex-1 min-w-0">
        <Breadcrumb
          items={[
            { label: 'Repos', to: '/' },
            { label: `${owner}/${repo}`, to: `/${owner}/${repo}` },
            { label: `#${pr.number}` },
          ]}
        />
        <h1 className="text-xl font-semibold text-gray-900 mb-1">{pr.title}</h1>
        <p className="text-sm text-gray-500 mb-6">
          {pr.author_login} &middot; {pr.head_branch} &rarr; {pr.base_branch} &middot;{' '}
          <span className="font-mono text-xs">{pr.head_sha.slice(0, 7)}</span>
        </p>
        <DiffViewer files={files} annotationsByFile={annotationsByFile} />
      </div>
      <SpecPanel />
    </div>
  );
}
