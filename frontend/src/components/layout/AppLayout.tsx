import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Header } from './Header';
import { MobileNav } from './MobileNav';
import { Footer } from './Footer';
import { useApiMode } from '@/context/ApiModeContext';
import { useLanguage } from '@/context/LanguageContext';
import { Layers } from 'lucide-react';

export const AppLayout: React.FC = () => {
  const { isMockMode } = useApiMode();
  const { t } = useLanguage();
  const location = useLocation();
  const isLanding = location.pathname === '/';

  return (
    <div className="min-h-screen flex flex-col bg-ivory text-navy font-sans antialiased selection:bg-saffron/20 selection:text-navy">
      <Header />

      {isMockMode && !isLanding && (
        <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 mt-3">
          <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-saffron-light/80 border border-saffron/20 text-saffron-dark text-xs font-medium">
            <Layers className="w-4 h-4 shrink-0 text-saffron" />
            <span>{t.labels.mockModeNotice}</span>
          </div>
        </div>
      )}

      <main className={`flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 ${isLanding ? 'py-2 sm:py-3' : 'py-6'}`}>
        <Outlet />
      </main>

      <Footer />
      <MobileNav />
    </div>
  );
};
