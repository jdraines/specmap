import { Link } from 'react-router';
import { useAuthStore } from '../../stores/authStore';

export function Header() {
  const { user, logout } = useAuthStore();

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="text-lg font-semibold text-gray-900 no-underline">
          Specmap
        </Link>
        {user && (
          <div className="flex items-center gap-3">
            <img
              src={user.avatar_url}
              alt={user.login}
              className="w-8 h-8 rounded-full"
            />
            <span className="text-sm text-gray-600">{user.login}</span>
            <button
              onClick={() => logout()}
              className="text-sm text-gray-500 hover:text-gray-700 cursor-pointer"
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
