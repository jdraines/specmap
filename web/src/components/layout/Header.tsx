import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { useAuthStore } from '../../stores/authStore';
import { useThemeStore } from '../../stores/themeStore';
import { settings } from '../../api/endpoints';

export function Header() {
  const { user, logout } = useAuthStore();
  const { theme, cycle } = useThemeStore();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [model, setModel] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [version, setVersion] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const themeLabel = theme === 'light' ? 'light' : theme === 'dark' ? 'dark' : 'sys';

  // Fetch version once on mount
  useEffect(() => {
    fetch('/healthz').then(r => r.json()).then(d => setVersion(d.version || '')).catch(() => {});
  }, []);

  // Load settings when dropdown opens
  useEffect(() => {
    if (settingsOpen) {
      settings.get().then((s) => setModel(s.model)).catch(() => {});
    }
  }, [settingsOpen]);

  // Close on click outside
  useEffect(() => {
    if (!settingsOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [settingsOpen]);

  const handleSave = useCallback(async () => {
    if (!model.trim()) return;
    setSaving(true);
    try {
      const result = await settings.update({ model: model.trim() });
      setModel(result.model);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }, [model]);

  return (
    <header className="border-b border-[var(--border)] bg-[var(--surface-1)]">
      <div className="px-4 h-12 flex items-center justify-between">
        <Link to="/" className="text-sm font-semibold text-[var(--text-primary)] no-underline tracking-tight">
          <span className="text-[var(--text-secondary)]">&gt;</span> specmap<span className="text-[var(--accent)]">_</span>
          {version && <span className="text-[10px] font-mono text-[var(--wt-border)] ml-1">{version}</span>}
        </Link>
        <div className="flex items-center gap-3">
          <button
            onClick={cycle}
            className="px-2 py-0.5 text-xs font-mono text-[var(--text-secondary)] cursor-pointer bg-transparent border border-[var(--border)] hover:border-[var(--border-strong)]"
            title={`Theme: ${theme}`}
          >
            {themeLabel}
          </button>

          {/* Settings dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setSettingsOpen(!settingsOpen)}
              className={`px-2 py-0.5 text-xs font-mono cursor-pointer bg-transparent border hover:border-[var(--border-strong)] ${
                settingsOpen
                  ? 'text-[var(--text-primary)] border-[var(--border-strong)]'
                  : 'text-[var(--text-secondary)] border-[var(--border)]'
              }`}
              title="Settings"
            >
              settings
            </button>
            {settingsOpen && (
              <div className="absolute right-0 top-full mt-1 w-72 bg-[var(--surface-1)] border border-[var(--border-strong)] shadow-lg p-3 z-[100]">
                <div className="text-xs font-medium text-[var(--text-primary)] mb-2">Settings</div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">Model</label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); }}
                  className="w-full px-2 py-1 text-xs border border-[var(--border)] bg-[var(--surface-0)] text-[var(--text-primary)] rounded mb-2 focus:outline-none focus:ring-1 focus:ring-[var(--focus-ring)]"
                  placeholder="e.g. anthropic/claude-sonnet-4-20250514"
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSave}
                    disabled={saving || !model.trim()}
                    className="px-2 py-1 text-xs font-medium bg-[var(--accent)] text-white border-0 rounded cursor-pointer hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                  {saved && (
                    <span className="text-xs text-[var(--insert-text)]">Saved</span>
                  )}
                </div>
              </div>
            )}
          </div>

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
                className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer bg-transparent border-0"
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
