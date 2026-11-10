import React, { createContext, useContext, useState } from 'react';
import { apiClient } from '@/services/api/client';

interface ApiModeContextType {
  isMockMode: boolean;
  setMockMode: (enabled: boolean) => void;
  apiBaseUrl: string;
}

const ApiModeContext = createContext<ApiModeContextType | undefined>(undefined);

export const ApiModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isMockMode, setIsMockModeState] = useState<boolean>(apiClient.isMockMode());

  const setMockMode = (enabled: boolean) => {
    apiClient.setMockMode(enabled);
    setIsMockModeState(enabled);
  };

  return (
    <ApiModeContext.Provider
      value={{
        isMockMode,
        setMockMode,
        apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
      }}
    >
      {children}
    </ApiModeContext.Provider>
  );
};

export const useApiMode = (): ApiModeContextType => {
  const context = useContext(ApiModeContext);
  if (!context) {
    throw new Error('useApiMode must be used within an ApiModeProvider');
  }
  return context;
};
