/**
 * Authentication context.
 *
 * Provides global auth state (user, token, isAuthenticated) and
 * login/logout/register actions to all child components.
 *
 * Usage:
 *   const { user, login, logout } = useAuth();
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  fetchCurrentUser,
  hasStoredToken,
  login as authLogin,
  logout as authLogout,
  register as authRegister,
} from '@/auth/authService';
import type { AuthResponse, LoginRequest, RegisterRequest, User } from '@/types/auth';

// ------------------------------------------------------------------ //
// Context shape
// ------------------------------------------------------------------ //
interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<AuthResponse>;
  register: (data: RegisterRequest) => Promise<AuthResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ------------------------------------------------------------------ //
// Provider
// ------------------------------------------------------------------ //
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // On mount: restore session from stored token
  useEffect(() => {
    const restore = async () => {
      if (hasStoredToken()) {
        const u = await fetchCurrentUser();
        setUser(u);
      }
      setIsLoading(false);
    };
    restore();
  }, []);

  const login = useCallback(async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await authLogin(data);
    setUser(response.user);
    return response;
  }, []);

  const register = useCallback(async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await authRegister(data);
    setUser(response.user);
    return response;
  }, []);

  const logout = useCallback(() => {
    authLogout();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      register,
      logout,
    }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ------------------------------------------------------------------ //
// Hook
// ------------------------------------------------------------------ //
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}
