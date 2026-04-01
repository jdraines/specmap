import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import type { Repository } from '../api/types';
import { repos } from '../api/endpoints';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

export function DashboardPage() {
  const [repoList, setRepoList] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    repos
      .list()
      .then(setRepoList)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-[var(--error-text)]">{error}</p>;

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-4">
        repositories
      </h1>
      {repoList.length === 0 ? (
        <div className="text-sm text-[var(--text-muted)] border border-[var(--border)] p-4">
          <p className="mb-2">No repositories found.</p>
          <p>
            The specmap GitHub App may not be installed on any of your repositories.
            Go to your GitHub settings to install the App and select which repositories to grant access to.
          </p>
        </div>
      ) : (
        <div className="border border-[var(--border)] divide-y divide-[var(--border)]">
          {repoList.map((r) => (
            <Link
              key={r.id}
              to={`/${r.owner}/${r.name}`}
              className="flex items-center justify-between px-4 py-2.5 hover:bg-[var(--hover-bg)] no-underline"
            >
              <span className="text-sm text-[var(--text-primary)]">{r.full_name}</span>
              {r.private && (
                <span className="text-[10px] text-[var(--text-muted)] border border-[var(--border)] px-1.5 py-0.5">
                  private
                </span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
