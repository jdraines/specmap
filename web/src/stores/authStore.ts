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
      const user = await auth.me();
      set({ user, loading: false });
    } catch {
      set({ user: null, loading: false });
    }
  },
  logout: async () => {
    await auth.logout();
    set({ user: null });
  },
}));
