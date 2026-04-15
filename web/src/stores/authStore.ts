import { create } from 'zustand';
import type { User } from '../api/types';
import { auth } from '../api/endpoints';

interface AuthState {
  user: User | null;
  loading: boolean;
  fetchUser: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  fetchUser: async () => {
    try {
      const status = await auth.status();
      if (status.authenticated && status.user) {
        set({ user: status.user, loading: false });
      } else {
        set({ user: null, loading: false });
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
