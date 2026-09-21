/**
 * Authentication TypeScript types.
 *
 * Mirror the backend Pydantic schemas exactly.
 * Keep in sync when backend schemas change.
 */

import type { UserRole } from './api';

// ------------------------------------------------------------------ //
// Re-export UserRole for convenience
// ------------------------------------------------------------------ //
export type { UserRole };

// ------------------------------------------------------------------ //
// User profile (mirrors UserResponse schema)
// ------------------------------------------------------------------ //
export interface User {
  id: string;           // UUID as string
  name: string;
  email: string;
  role: 'USER' | 'ADMIN';
  is_active: boolean;
  created_at: string;   // ISO 8601
  updated_at: string;   // ISO 8601
}

// ------------------------------------------------------------------ //
// Request payloads
// ------------------------------------------------------------------ //
export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ------------------------------------------------------------------ //
// API responses
// ------------------------------------------------------------------ //
export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  user: User;
}

// ------------------------------------------------------------------ //
// Auth context state shape
// ------------------------------------------------------------------ //
export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
