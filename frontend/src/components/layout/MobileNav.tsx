import React from 'react';
import { NavLink } from 'react-router-dom';
import { useLanguage } from '@/context/LanguageContext';
import { BookOpen, Sparkles, FolderKanban, LayoutDashboard, Home } from 'lucide-react';
import { cn } from '@/utils/cn';

export const MobileNav: React.FC = () => {
  const { t } = useLanguage();

  const links = [
    { to: '/', label: t.nav.home, icon: Home },
    { to: '/schemes', label: t.nav.schemes, icon: BookOpen },
    { to: '/chat', label: t.nav.chat, icon: Sparkles, highlight: true },
    { to: '/applications', label: t.nav.applications, icon: FolderKanban },
    { to: '/dashboard', label: t.nav.dashboard, icon: LayoutDashboard },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-navy/8 pb-safe">
      <div className="flex items-center justify-around h-16 px-2">
        {links.map((link) => {
          const Icon = link.icon;
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center justify-center w-full py-1 text-[11px] font-medium transition-all duration-200',
                  link.highlight
                    ? isActive
                      ? 'text-saffron-dark font-bold scale-105'
                      : 'text-saffron font-semibold'
                    : isActive
                    ? 'text-navy font-bold'
                    : 'text-navy/50 hover:text-navy'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <div
                    className={cn(
                      'p-1.5 rounded-xl transition-all duration-200',
                      link.highlight && 'bg-saffron-light text-saffron shadow-subtle',
                      isActive && !link.highlight && 'bg-navy/5 text-navy'
                    )}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="mt-0.5 truncate max-w-[64px] text-[10px]">{link.label}</span>
                </>
              )}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
};
