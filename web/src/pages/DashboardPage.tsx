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
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <h1 className="text-xl font-semibold text-gray-900 mb-4">Repositories</h1>
      {repoList.length === 0 ? (
        <p className="text-gray-500">No repositories found.</p>
      ) : (
        <div className="grid gap-3">
          {repoList.map((r) => (
            <Link
              key={r.id}
              to={`/${r.owner}/${r.name}`}
              className="block bg-white rounded-lg border border-gray-200 p-4 hover:border-blue-300 no-underline"
            >
              <div className="font-medium text-gray-900">{r.full_name}</div>
              {r.private && (
                <span className="text-xs text-gray-500 bg-gray-100 rounded px-1.5 py-0.5 mt-1 inline-block">
                  Private
                </span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
