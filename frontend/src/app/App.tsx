import React from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { LanguageProvider } from '@/context/LanguageContext';
import { AuthProvider } from '@/context/AuthContext';
import { ApiModeProvider } from '@/context/ApiModeContext';

export const App: React.FC = () => {
  return (
    <ApiModeProvider>
      <LanguageProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </LanguageProvider>
    </ApiModeProvider>
  );
};
