import { useEffect } from 'react';
import { Routes, Route } from 'react-router';
import { useAuthStore } from './stores/authStore';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { RepoSplatRouter } from './pages/RepoSplatRouter';
import { LoadingSpinner } from './components/ui/LoadingSpinner';

export default function App() {
  const { user, loading, fetchUser } = useAuthStore();

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--surface-0)]">
        <LoadingSpinner />
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/r/*" element={<RepoSplatRouter />} />
      </Routes>
    </AppShell>
  );
}
