/**
 * ProtectedRoute — guards routes that require authentication and specific roles.
 *
 * Behavior:
 *   - Unauthenticated users → redirect to /login
 *   - Authenticated users with insufficient role (e.g. USER accessing ADMIN route) → redirect to /chat
 *   - While auth state is initializing from token → show loading spinner
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import type { UserRole } from '@/types/api';

interface ProtectedRouteProps {
  requiredRole?: UserRole;
}

export function ProtectedRoute({ requiredRole }: ProtectedRouteProps) {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface-bg flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          <p className="text-slate-400 text-sm">Checking authentication…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole && user.role !== requiredRole) {
    // Insufficient permissions (e.g. normal USER accessing ADMIN route)
    return <Navigate to="/chat" replace />;
  }

  return <Outlet />;
}
