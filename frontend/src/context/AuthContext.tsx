import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: { email: string; password: string; full_name: string; preferred_language?: string }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('scheme_saathi_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    const storedToken = localStorage.getItem('scheme_saathi_token');
    if (!storedToken) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const userData = await api.auth.getMe();
      setUser(userData);
    } catch (err) {
      console.error('Failed to restore session:', err);
      localStorage.removeItem('scheme_saathi_token');
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, [token]);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const authData = await api.auth.login(email, password);
      const accessToken = authData.access_token;
      localStorage.setItem('scheme_saathi_token', accessToken);
      setToken(accessToken);
      if (authData.user) {
        setUser(authData.user);
      } else {
        await refreshUser();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: { email: string; password: string; full_name: string; preferred_language?: string }) => {
    setIsLoading(true);
    try {
      const authData = await api.auth.register(payload);
      const accessToken = authData.access_token;
      localStorage.setItem('scheme_saathi_token', accessToken);
      setToken(accessToken);
      if (authData.user) {
        setUser(authData.user);
      } else {
        await refreshUser();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('scheme_saathi_token');
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
