import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserProfile } from '@/types';
import { apiClient } from '@/services/api/client';
import { profileService } from '@/services/api/profileService';
import { authService, RegisterRequest } from '@/services/api/authService';
import { MOCK_USER_PROFILE } from '@/services/mock/mockData';

interface AuthCredentials {
  email?: string;
  password?: string;
  token?: string;
}

interface AuthContextType {
  user: { id: string; email?: string } | null;
  profile: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials?: AuthCredentials | string) => Promise<UserProfile | null>;
  register: (data: RegisterRequest) => Promise<UserProfile | null>;
  logout: () => void;
  refreshProfile: () => Promise<UserProfile | null>;
  updateProfileState: (updated: UserProfile) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(apiClient.getToken());
  const [user, setUser] = useState<{ id: string; email?: string } | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshProfile = async (): Promise<UserProfile | null> => {
    try {
      const p = await profileService.getProfile();
      setProfile(p);
      if (p) {
        setUser({ id: p.user_id, email: `${p.full_name?.toLowerCase().replace(/\s+/g, '') || 'citizen'}@example.gov.in` });
      }
      return p;
    } catch {
      if (apiClient.isMockMode()) {
        setProfile(MOCK_USER_PROFILE);
        setUser({ id: MOCK_USER_PROFILE.user_id, email: 'ramesh.farmer@example.com' });
        return MOCK_USER_PROFILE;
      } else {
        setProfile(null);
        setUser(null);
        return null;
      }
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      if (token || apiClient.isMockMode()) {
        await refreshProfile();
      }
      setIsLoading(false);
    };
    initAuth();
  }, [token]);

  const login = async (credentials?: AuthCredentials | string): Promise<UserProfile | null> => {
    if (typeof credentials === 'string') {
      const activeToken = credentials || 'mock-demo-jwt-token-scheme-saathi';
      apiClient.setToken(activeToken);
      setToken(activeToken);
      return await refreshProfile();
    }

    if (apiClient.isMockMode()) {
      const activeToken = credentials?.token || 'mock-demo-jwt-token-scheme-saathi';
      apiClient.setToken(activeToken);
      setToken(activeToken);
      return await refreshProfile();
    }

    const email = credentials?.email || 'ramesh.farmer@example.gov.in';
    const password = credentials?.password || 'SecureCitizenPassword123!';
    const res = await authService.login({ email, password });
    apiClient.setToken(res.access_token);
    setToken(res.access_token);
    return await refreshProfile();
  };

  const register = async (data: RegisterRequest): Promise<UserProfile | null> => {
    if (apiClient.isMockMode()) {
      const activeToken = 'mock-new-citizen-token';
      apiClient.setToken(activeToken);
      setToken(activeToken);
      const newMockProfile: UserProfile = {
        id: 'mock-new-profile-id',
        user_id: 'mock-new-user-id',
        full_name: data.full_name || '',
        preferred_language: 'hi',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setProfile(newMockProfile);
      setUser({ id: 'mock-new-user-id', email: data.email });
      return newMockProfile;
    }

    const res = await authService.register(data);
    apiClient.setToken(res.access_token);
    setToken(res.access_token);
    return await refreshProfile();
  };

  const logout = () => {
    apiClient.setToken(null);
    setToken(null);
    setUser(null);
    setProfile(null);
  };

  const updateProfileState = (updated: UserProfile) => {
    setProfile(updated);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        token,
        isAuthenticated: !!token || apiClient.isMockMode(),
        isLoading,
        login,
        register,
        logout,
        refreshProfile,
        updateProfileState,
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
