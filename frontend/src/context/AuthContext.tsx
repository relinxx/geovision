/**
 * Authentication Context
 * ======================
 * Provides authentication state and methods throughout the application.
 * Manages JWT tokens, user data, and authentication flows.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';

/** User data structure */
interface User {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

/** Authentication context type */
interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, username: string, password: string) => Promise<boolean>;
  logout: () => void;
  getToken: () => string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/** API base URL */
const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
const IS_DEV = Boolean((import.meta as any).env?.DEV);

function buildApiBaseCandidates(baseUrl: string): string[] {
  const candidates: string[] = [];
  const pushCandidate = (value: string) => {
    const normalized = String(value || '').replace(/\/+$/, '');
    if (!normalized || candidates.includes(normalized)) {
      return;
    }
    candidates.push(normalized);
  };

  if (typeof window !== 'undefined' && window.location?.hostname) {
    const protocol = window.location.protocol || 'http:';
    const hostname = window.location.hostname;
    const origin = window.location.origin?.replace(/\/+$/, '');
    if (IS_DEV && origin) {
      pushCandidate(origin);
    }
    pushCandidate(baseUrl);
    pushCandidate(origin);
    pushCandidate(`${protocol}//${hostname}:8000`);
    pushCandidate(`${protocol}//${hostname}:8001`);
    pushCandidate(`${protocol}//localhost:8000`);
    pushCandidate(`${protocol}//localhost:8001`);
    pushCandidate(`${protocol}//127.0.0.1:8000`);
    pushCandidate(`${protocol}//127.0.0.1:8001`);
  } else {
    pushCandidate(baseUrl);
  }

  pushCandidate('http://localhost:8000');
  pushCandidate('http://localhost:8001');
  pushCandidate('http://127.0.0.1:8000');
  pushCandidate('http://127.0.0.1:8001');

  return candidates;
}

async function authRequest<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const baseCandidates = buildApiBaseCandidates(API_BASE_URL);
  let lastError: Error | null = null;

  for (let index = 0; index < baseCandidates.length; index += 1) {
    const base = baseCandidates[index];
    const url = `${base}${endpoint}`;

    try {
      const response = await fetch(url, options);
      const text = await response.text();

      if (!response.ok) {
        let parsed: any = null;
        try {
          parsed = text ? JSON.parse(text) : null;
        } catch {
          parsed = null;
        }

        const error: any = new Error(parsed?.detail || text || `Request failed: ${response.status}`);
        error.status = response.status;
        throw error;
      }

      return text ? (JSON.parse(text) as T) : ({} as T);
    } catch (error: any) {
      lastError = error instanceof Error ? error : new Error(String(error));
      const isNetworkError =
        error instanceof TypeError || /Failed to fetch|NetworkError/i.test(String(error?.message || ''));
      const hasMoreCandidates = index < baseCandidates.length - 1;

      if (isNetworkError && hasMoreCandidates) {
        console.warn(`[Auth] Network error on ${url}; trying next base URL`);
        continue;
      }

      throw lastError;
    }
  }

  throw lastError || new Error(`Authentication request failed for ${endpoint}`);
}

/**
 * Authentication Provider component.
 * Wraps the application to provide auth state and methods.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session from localStorage immediately — no network wait before render
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const storedUser = localStorage.getItem('user');

    if (token && storedUser) {
      try {
        const parsed: User = JSON.parse(storedUser);
        setUser(parsed);  // optimistic — show page immediately
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
      }
    }

    // Loading done — page renders now regardless of token state
    setIsLoading(false);

    // Background validation: silently log out if token is expired/invalid
    if (token) {
      validateToken(token).then((valid) => {
        if (!valid) setUser(null);
      }).catch(() => {
        // Network error — keep the optimistic session
      });
    }
  }, []);

  /** Validate token with backend — returns true if valid */
  const validateToken = async (token: string): Promise<boolean> => {
    try {
      await authRequest(`/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      return true;
    } catch (error: any) {
      if (error?.status === 401 || error?.status === 403) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        return false;
      }
      // Backend unreachable — treat stored session as valid to avoid locking out offline users
      return true;
    }
  };

  /** Login user */
  const login = useCallback(async (email: string, password: string): Promise<boolean> => {
    try {
      const data = await authRequest<{ access_token: string; user: User }>(`/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email, password })
      });
      
      // Store token and user data
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      setUser(data.user);
      toast.success(`Welcome back, ${data.user.username}!`);
      return true;
    } catch (error: any) {
      toast.error(error?.message || 'Network error. Please try again.');
      console.error('Login error:', error);
      return false;
    }
  }, []);

  /** Register user */
  const register = useCallback(async (email: string, username: string, password: string): Promise<boolean> => {
    try {
      const data = await authRequest<{ access_token: string; user: User }>(`/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email, username, password })
      });
      
      // Store token and user data
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      setUser(data.user);
      toast.success(`Welcome, ${data.user.username}! Account created successfully.`);
      return true;
    } catch (error: any) {
      toast.error(error?.message || 'Network error. Please try again.');
      console.error('Registration error:', error);
      return false;
    }
  }, []);

  /** Logout user */
  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setUser(null);
    toast.success('Logged out successfully');
  }, []);

  /** Get current token */
  const getToken = useCallback(() => {
    return localStorage.getItem('access_token');
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    getToken
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to use authentication context.
 * @throws Error if used outside AuthProvider
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
