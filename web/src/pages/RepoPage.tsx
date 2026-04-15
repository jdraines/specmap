import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import type { PullRequest } from '../api/types';
import { pulls as pullsApi } from '../api/endpoints';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Breadcrumb } from '../components/ui/Breadcrumb';

interface RepoPageProps {
  fullName: string;
}

export function RepoPage({ fullName }: RepoPageProps) {
  const [pullList, setPullList] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!fullName) return;
    pullsApi
      .list(fullName)
      .then(setPullList)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [fullName]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-[var(--error-text)]">{error}</p>;

  return (
    <div className="max-w-3xl mx-auto">
      <Breadcrumb items={[{ label: 'repos', to: '/' }, { label: fullName }]} />
      <h1 className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-4">
        open pull requests
      </h1>
      {pullList.length === 0 ? (
        <p className="text-[var(--text-muted)]">No open pull requests.</p>
      ) : (
        <div className="border border-[var(--border)] divide-y divide-[var(--border)]">
          {pullList.map((pr) => (
            <Link
              key={pr.id}
              to={`/r/${fullName}/pull/${pr.number}`}
              className="flex items-start gap-3 px-4 py-2.5 hover:bg-[var(--hover-bg)] no-underline"
            >
              <span className="text-[var(--text-muted)] text-xs pt-0.5">#{pr.number}</span>
              <div className="min-w-0 flex-1">
                <div className="text-sm text-[var(--text-primary)] truncate">{pr.title}</div>
                <div className="text-xs text-[var(--text-muted)] mt-0.5">
                  {pr.author_login} &middot; {pr.head_branch} &rarr; {pr.base_branch}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
