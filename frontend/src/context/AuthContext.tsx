import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserProfile } from '@/types';
import { apiClient } from '@/services/api/client';
import { profileService } from '@/services/api/profileService';
import { MOCK_USER_PROFILE } from '@/services/mock/mockData';

interface AuthContextType {
  user: { id: string; email?: string } | null;
  profile: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token?: string) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
  updateProfileState: (updated: UserProfile) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(apiClient.getToken());
  const [user, setUser] = useState<{ id: string; email?: string } | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshProfile = async () => {
    try {
      const p = await profileService.getProfile();
      setProfile(p);
      if (p) {
        setUser({ id: p.user_id, email: `${p.full_name.toLowerCase().replace(/\s+/g, '')}@example.gov.in` });
      }
    } catch {
      // In mock mode or if network is down
      if (apiClient.isMockMode()) {
        setProfile(MOCK_USER_PROFILE);
        setUser({ id: MOCK_USER_PROFILE.user_id, email: 'ramesh.farmer@example.com' });
      } else {
        setProfile(null);
        setUser(null);
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

  const login = async (newToken?: string) => {
    const activeToken = newToken || 'mock-demo-jwt-token-scheme-saathi';
    apiClient.setToken(activeToken);
    setToken(activeToken);
    await refreshProfile();
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
