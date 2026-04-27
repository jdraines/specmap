import { create } from 'zustand';
import type { User } from '../api/types';
import { auth } from '../api/endpoints';

interface AuthState {
  user: User | null;
  currentRepo: string | null;
  loading: boolean;
  didAutoRedirect: boolean;
  fetchUser: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  currentRepo: null,
  loading: true,
  didAutoRedirect: false,
  fetchUser: async () => {
    try {
      const status = await auth.status();
      if (status.authenticated && status.user) {
        set({ user: status.user, currentRepo: status.current_repo ?? null, loading: false });
      } else {
        set({ user: null, currentRepo: status.current_repo ?? null, loading: false });
      }
    } catch {
      set({ user: null, loading: false });
    }
  },
  logout: async () => {
    await auth.logout();
    set({ user: null });
  },
}));
