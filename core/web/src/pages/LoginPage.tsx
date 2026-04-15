import { useEffect, useState } from 'react';
import type { AuthStatus } from '../api/types';
import { auth } from '../api/endpoints';
import { useAuthStore } from '../stores/authStore';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

const GitHubIcon = () => (
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
  </svg>
);

const GitLabIcon = () => (
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
    <path d="M23.955 13.587l-1.342-4.135-2.664-8.189a.455.455 0 0 0-.867 0L16.418 9.45H7.582L4.918 1.263a.455.455 0 0 0-.867 0L1.386 9.452.045 13.587a.924.924 0 0 0 .331 1.023L12 23.054l11.624-8.443a.92.92 0 0 0 .331-1.024" />
  </svg>
);

export function LoginPage() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokenInput, setTokenInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const { fetchUser } = useAuthStore();

  useEffect(() => {
    auth
      .status()
      .then((s) => {
        if (s.authenticated) {
          // Already authenticated — refresh user and let App redirect
          fetchUser();
        } else {
          setStatus(s);
        }
      })
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, [fetchUser]);

  if (loading) return <LoadingSpinner />;

  const provider = status?.provider ?? 'github';
  const ProviderIcon = provider === 'gitlab' ? GitLabIcon : GitHubIcon;
  const providerLabel = provider === 'gitlab' ? 'GitLab' : 'GitHub';

  const handleTokenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      await auth.submitToken(tokenInput.trim());
      await fetchUser();
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--surface-0)]">
      <div className="bg-[var(--surface-1)] border border-[var(--border)] p-8 max-w-sm w-full text-center">
        <div className="text-lg font-semibold text-[var(--text-primary)] mb-1">
          <span className="text-[var(--text-muted)]">&gt;</span> specmap
          <span className="text-[var(--accent)]">_</span>
        </div>
        <p className="text-sm text-[var(--text-muted)] mb-1">review PRs with spec annotations</p>
        <p className="text-xs text-[var(--text-muted)] mb-6">
          detected forge: <span className="text-[var(--text-secondary)]">{providerLabel}</span>
        </p>

        {status?.auth_mode === 'oauth' ? (
          <a
            href={`/api/v1/auth/login/${provider}`}
            className="inline-flex items-center gap-2 bg-[var(--text-primary)] text-[var(--surface-0)] px-6 py-2 text-sm hover:opacity-90 no-underline"
          >
            <ProviderIcon />
            sign in with {providerLabel}
          </a>
        ) : (
          <div className="text-left">
            {status?.setup_hint && (
              <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{status.setup_hint}</p>
            )}
            <form onSubmit={handleTokenSubmit}>
              <label className="block text-xs text-[var(--text-muted)] mb-1">
                personal access token
              </label>
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder={provider === 'gitlab' ? 'glpat-...' : 'ghp_...'}
                className="w-full px-3 py-1.5 text-sm bg-[var(--surface-0)] border border-[var(--border)] text-[var(--text-primary)] font-mono mb-3 outline-none focus:border-[var(--accent)]"
              />
              <button
                type="submit"
                disabled={submitting || !tokenInput.trim()}
                className="w-full inline-flex items-center justify-center gap-2 bg-[var(--text-primary)] text-[var(--surface-0)] px-6 py-2 text-sm hover:opacity-90 disabled:opacity-50 cursor-pointer border-0"
              >
                <ProviderIcon />
                {submitting ? 'authenticating...' : `sign in with ${providerLabel} token`}
              </button>
            </form>
            {error && <p className="text-xs text-[var(--error-text)] mt-2">{error}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
