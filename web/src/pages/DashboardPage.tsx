import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import type { PaginatedResponse, Repository } from '../api/types';
import { repos } from '../api/endpoints';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

export function DashboardPage() {
  const [data, setData] = useState<PaginatedResponse<Repository> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const fetchId = useRef(0);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  // Fetch on page or debouncedSearch change
  useEffect(() => {
    const id = ++fetchId.current;
    setLoading(true);
    repos
      .list({ page, per_page: PAGE_SIZE, search: debouncedSearch || undefined })
      .then((result) => {
        if (id === fetchId.current) setData(result);
      })
      .catch((err) => {
        if (id === fetchId.current) setError(String(err));
      })
      .finally(() => {
        if (id === fetchId.current) setLoading(false);
      });
  }, [page, debouncedSearch]);

  if (!data && loading) return <LoadingSpinner />;
  if (error) return <p className="text-[var(--error-text)]">{error}</p>;

  const items = data?.items ?? [];
  const totalPages = data?.total_pages ?? 1;
  const currentPage = data?.page ?? 1;

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-4">
        repositories
      </h1>

      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search repositories..."
        className="w-full mb-4 px-3 py-2 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] outline-none focus:border-[var(--text-muted)]"
      />

      {items.length === 0 && !loading ? (
        <div className="text-sm text-[var(--text-muted)] border border-[var(--border)] p-4">
          {debouncedSearch ? (
            <p>No repositories match &ldquo;{debouncedSearch}&rdquo;.</p>
          ) : (
            <>
              <p className="mb-2">No repositories found.</p>
              <p>Check that your token has access to repositories.</p>
            </>
          )}
        </div>
      ) : (
        <>
          <div className={`border border-[var(--border)] divide-y divide-[var(--border)]${loading ? ' opacity-60' : ''}`}>
            {items.map((r) => (
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
