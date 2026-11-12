import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '@/context/LanguageContext';
import { useAuth } from '@/context/AuthContext';
import { useApiMode } from '@/context/ApiModeContext';
import { User } from 'lucide-react';
import { cn } from '@/utils/cn';
import { LoginModal } from '@/components/common/LoginModal';
import logoOriginal from '@/assets/logo-original.png';
import logoOriginal2x from '@/assets/logo-original@2x.png';

export const Header: React.FC = () => {
  const { language, setLanguage, t } = useLanguage();
  const { profile, token } = useAuth();
  const { isMockMode, setMockMode } = useApiMode();
  const location = useLocation();
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  const navLinks = [
    { to: '/', label: t.nav.home },
    { to: '/schemes', label: t.nav.schemes },
    { to: '/eligible', label: t.nav.eligibility },
    { to: '/chat', label: t.nav.chat },
    { to: '/applications', label: t.nav.applications },
  ];

  return (
    <header className="sticky top-0 z-40 bg-ivory/95 backdrop-blur-md transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Authentic Scheme Saathi Logo from Approved Reference */}
          <Link to="/" className="flex items-center group py-1" aria-label="Scheme Saathi Home">
            <img
              src={logoOriginal2x}
              srcSet={`${logoOriginal} 1x, ${logoOriginal2x} 2x`}
              alt="Scheme Saathi"
              className="h-9 sm:h-10 w-auto object-contain transition-transform duration-200 group-hover:scale-[1.02]"
            />
          </Link>

          {/* Center Navigation Links with Active Saffron Underline */}
          <nav className="hidden md:flex items-center gap-7 lg:gap-9 text-sm font-medium">
            {navLinks.map((link) => {
              const isActive =
                link.to === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(link.to);
              return (
                <Link
                  key={link.label}
                  to={link.to}
                  className={cn(
                    'relative py-1 transition-colors duration-200',
                    isActive
                      ? 'text-navy font-semibold after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-saffron after:rounded-full'
                      : 'text-navy/70 hover:text-navy'
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>

          {/* Right Action Controls: Language Toggle, Mock/Live Pill, Login Button */}
          <div className="flex items-center gap-3 sm:gap-4">
            {/* Minimal Language Switcher: English | हिन्दी | मराठी */}
            <div className="flex items-center gap-1.5 text-xs font-semibold text-navy bg-white/80 border border-navy/10 px-2.5 py-1 rounded-full shadow-subtle">
              <button
                onClick={() => setLanguage('en')}
                className={cn(
                  'transition-colors px-1 py-0.5 rounded',
                  language === 'en' ? 'text-saffron-dark font-bold underline underline-offset-2' : 'text-navy/60 hover:text-navy'
                )}
                title="Switch interface language to English"
              >
                English
              </button>
              <span className="text-navy/20">|</span>
              <button
                onClick={() => setLanguage('hi')}
                className={cn(
                  'transition-colors px-1 py-0.5 rounded',
                  language === 'hi' ? 'text-saffron-dark font-bold underline underline-offset-2' : 'text-navy/60 hover:text-navy'
                )}
                title="इंटरफेस भाषा हिंदी में बदलें"
              >
                हिन्दी
              </button>
              <span className="text-navy/20">|</span>
              <button
                onClick={() => setLanguage('mr')}
                className={cn(
                  'transition-colors px-1 py-0.5 rounded',
                  language === 'mr' ? 'text-saffron-dark font-bold underline underline-offset-2' : 'text-navy/60 hover:text-navy'
                )}
                title="इंटरफेस भाषा मराठीत बदला"
              >
                मराठी
              </button>
            </div>

            {/* Mock / Live Backend Pill with Green Dot */}
            <button
              onClick={() => setMockMode(!isMockMode)}
              title={isMockMode ? "Currently using mock data. Click to toggle live API." : "Connected to live API."}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-white border border-navy/10 shadow-subtle hover:border-navy/20 transition-all duration-200"
            >
              <span className={cn('w-2 h-2 rounded-full', isMockMode ? 'bg-sage-pill' : 'bg-emerald-600')} />
              <span className="text-navy font-medium hidden sm:inline">{isMockMode ? 'Mock Data' : 'Live API'}</span>
            </button>

            {/* Pill Login Button in Deep Navy */}
            <button
              onClick={() => setIsLoginOpen(true)}
              className="flex items-center gap-2 px-5 py-2 rounded-full bg-navy text-white text-xs font-semibold hover:bg-navy-800 transition-all duration-200 shadow-subtle hover:shadow-premium"
            >
              <User className="w-3.5 h-3.5" />
              <span>{token && profile?.full_name ? profile.full_name.split(' ')[0] : 'Login'}</span>
            </button>
          </div>
        </div>
      </div>

      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </header>
  );
};
