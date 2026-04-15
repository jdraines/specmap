import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import type { Repository } from '../api/types';
import { repos } from '../api/endpoints';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

const PAGE_SIZE = 20;

export function DashboardPage() {
  const [repoList, setRepoList] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    repos
      .list()
      .then(setRepoList)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () =>
      search
        ? repoList.filter((r) => r.full_name.toLowerCase().includes(search.toLowerCase()))
        : repoList,
    [repoList, search],
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageRepos = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // Reset page when search changes
  useEffect(() => {
    setPage(1);
  }, [search]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-[var(--error-text)]">{error}</p>;

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-4">
        repositories
      </h1>

      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Filter repositories..."
        className="w-full mb-4 px-3 py-2 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] outline-none focus:border-[var(--text-muted)]"
      />

      {filtered.length === 0 ? (
        <div className="text-sm text-[var(--text-muted)] border border-[var(--border)] p-4">
          {repoList.length === 0 ? (
            <>
              <p className="mb-2">No repositories found.</p>
              <p>Check that your token has access to repositories.</p>
            </>
          ) : (
            <p>No repositories match &ldquo;{search}&rdquo;.</p>
          )}
        </div>
      ) : (
        <>
          <div className="border border-[var(--border)] divide-y divide-[var(--border)]">
            {pageRepos.map((r) => (
              <div
                key={r.id}
                className="flex items-center justify-between px-4 py-2.5 hover:bg-[var(--hover-bg)]"
              >
                <Link
                  to={`/${r.owner}/${r.name}`}
                  className="text-sm text-[var(--text-primary)] no-underline hover:underline"
                >
                  {r.full_name}
                </Link>
                <div className="flex items-center gap-2">
                  {r.recent_pulls?.map((pr) => (
                    <Link
                      key={pr.number}
                      to={`/${r.owner}/${r.name}/pull/${pr.number}`}
                      title={pr.title}
                      className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] no-underline"
                    >
                      #{pr.number}
                    </Link>
                  ))}
                  {r.private && (
                    <span className="text-[10px] text-[var(--text-muted)] border border-[var(--border)] px-1.5 py-0.5">
                      private
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 text-sm text-[var(--text-muted)]">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="px-3 py-1 border border-[var(--border)] bg-[var(--bg-primary)] text-[var(--text-muted)] disabled:opacity-40 hover:bg-[var(--hover-bg)] disabled:hover:bg-[var(--bg-primary)]"
              >
                prev
              </button>
              <span>
                {currentPage} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                className="px-3 py-1 border border-[var(--border)] bg-[var(--bg-primary)] text-[var(--text-muted)] disabled:opacity-40 hover:bg-[var(--hover-bg)] disabled:hover:bg-[var(--bg-primary)]"
              >
                next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
