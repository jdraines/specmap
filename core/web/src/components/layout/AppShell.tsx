import type { ReactNode } from 'react';
import { Header } from './Header';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--surface-0)]">
      <Header />
      <main className="px-4 py-6">{children}</main>
    </div>
  );
}
