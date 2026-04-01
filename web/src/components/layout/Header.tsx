import { Link } from 'react-router';
import { useAuthStore } from '../../stores/authStore';
import { useThemeStore } from '../../stores/themeStore';

export function Header() {
  const { user, logout } = useAuthStore();
  const { theme, cycle } = useThemeStore();

  const themeLabel = theme === 'light' ? 'light' : theme === 'dark' ? 'dark' : 'sys';

  return (
    <header className="border-b border-[var(--border)] bg-[var(--surface-1)]">
      <div className="px-4 h-12 flex items-center justify-between">
        <Link to="/" className="text-sm font-semibold text-[var(--text-primary)] no-underline tracking-tight">
          <span className="text-[var(--text-muted)]">&gt;</span> specmap<span className="text-[var(--accent)]">_</span>
        </Link>
        <div className="flex items-center gap-3">
          <button
            onClick={cycle}
            className="px-2 py-0.5 text-xs font-mono text-[var(--text-muted)] hover:text-[var(--text-secondary)] cursor-pointer bg-transparent border border-[var(--border)] hover:border-[var(--text-muted)]"
            title={`Theme: ${theme}`}
          >
            {themeLabel}
          </button>
          {user && (
            <>
              <img
                src={user.avatar_url}
                alt={user.login}
                className="w-6 h-6 rounded-full"
              />
              <span className="text-xs text-[var(--text-secondary)]">{user.login}</span>
              <button
                onClick={() => logout()}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer bg-transparent border-0"
              >
                logout
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
