import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router';
import type { PullRequest } from '../api/types';
import { pulls as pullsApi } from '../api/endpoints';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Breadcrumb } from '../components/ui/Breadcrumb';

export function RepoPage() {
  const { owner, repo } = useParams<{ owner: string; repo: string }>();
  const [pullList, setPullList] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!owner || !repo) return;
    pullsApi
      .list(owner, repo)
      .then(setPullList)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [owner, repo]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <Breadcrumb items={[{ label: 'Repos', to: '/' }, { label: `${owner}/${repo}` }]} />
      <h1 className="text-xl font-semibold text-gray-900 mb-4">Open Pull Requests</h1>
      {pullList.length === 0 ? (
        <p className="text-gray-500">No open pull requests.</p>
      ) : (
        <div className="grid gap-3">
          {pullList.map((pr) => (
            <Link
              key={pr.id}
              to={`/${owner}/${repo}/pull/${pr.number}`}
              className="block bg-white rounded-lg border border-gray-200 p-4 hover:border-blue-300 no-underline"
            >
              <div className="flex items-start gap-3">
                <span className="text-gray-400 font-mono text-sm">#{pr.number}</span>
                <div>
                  <div className="font-medium text-gray-900">{pr.title}</div>
                  <div className="text-sm text-gray-500 mt-1">
                    {pr.author_login} &middot; {pr.head_branch} &rarr; {pr.base_branch}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
