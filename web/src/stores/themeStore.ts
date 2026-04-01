import { create } from 'zustand';

type ThemeChoice = 'light' | 'dark' | 'system';
type ResolvedTheme = 'light' | 'dark';

interface ThemeState {
  theme: ThemeChoice;
  resolved: ResolvedTheme;
  setTheme: (theme: ThemeChoice) => void;
  cycle: () => void;
}

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolve(theme: ThemeChoice): ResolvedTheme {
  return theme === 'system' ? getSystemTheme() : theme;
}

function applyTheme(resolved: ResolvedTheme) {
  document.documentElement.classList.toggle('dark', resolved === 'dark');
}

const stored = (localStorage.getItem('specmap-theme') as ThemeChoice | null) ?? 'system';
const initialResolved = resolve(stored);
applyTheme(initialResolved);

export const useThemeStore = create<ThemeState>((set, get) => {
  const mql = window.matchMedia('(prefers-color-scheme: dark)');
  mql.addEventListener('change', () => {
    const { theme } = get();
    if (theme === 'system') {
      const resolved = resolve('system');
      applyTheme(resolved);
      set({ resolved });
    }
  });

  return {
    theme: stored,
    resolved: initialResolved,
    setTheme: (theme) => {
      const resolved = resolve(theme);
      localStorage.setItem('specmap-theme', theme);
      applyTheme(resolved);
      set({ theme, resolved });
    },
    cycle: () => {
      const order: ThemeChoice[] = ['light', 'system', 'dark'];
      const current = get().theme;
      const next = order[(order.indexOf(current) + 1) % order.length];
      get().setTheme(next);
    },
  };
});
