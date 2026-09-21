/**
 * Auth service — higher-level authentication operations.
 *
 * Wraps the raw API calls from services/api.ts with token
 * persistence (localStorage) so components don't handle storage.
 */

import { ACCESS_TOKEN_KEY, getCurrentUser, loginUser, registerUser } from '@/services/api';
import type { AuthResponse, LoginRequest, RegisterRequest, User } from '@/types/auth';

/**
 * Register a new user.
 * Persists the returned token to localStorage on success.
 */
export async function register(data: RegisterRequest): Promise<AuthResponse> {
  const response = await registerUser(data);
  localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
  return response;
}

/**
 * Log in with email and password.
 * Persists the returned token to localStorage on success.
 */
export async function login(data: LoginRequest): Promise<AuthResponse> {
  const response = await loginUser(data);
  localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
  return response;
}

/**
 * Fetch the currently authenticated user profile.
 * Returns null if not authenticated or token is invalid.
 */
export async function fetchCurrentUser(): Promise<User | null> {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (!token) return null;
  try {
    return await getCurrentUser();
  } catch {
    // Token invalid or expired — clear it
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    return null;
  }
}

/**
 * Log out by clearing the stored token.
 * Stateless JWT design — no server-side revocation in Phase 2.
 */
export function logout(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

/** Check whether a token is currently stored. */
export function hasStoredToken(): boolean {
  return Boolean(localStorage.getItem(ACCESS_TOKEN_KEY));
}
