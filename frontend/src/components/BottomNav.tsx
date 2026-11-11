import React from 'react';
import { NavLink } from 'react-router-dom';
import { useLanguage } from '../context/LanguageContext';
import { Sparkles, Compass, FileCheck2, FileText, Clock } from 'lucide-react';

export const BottomNav: React.FC = () => {
  const { t } = useLanguage();

  const navItems = [
    { to: '/', label: t('nav.chat'), icon: Sparkles },
    { to: '/schemes', label: t('nav.schemes'), icon: Compass },
    { to: '/documents', label: t('nav.documents'), icon: FileCheck2 },
    { to: '/applications', label: t('nav.applications'), icon: FileText },
    { to: '/tracking', label: t('nav.tracking'), icon: Clock },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur border-t border-slate-200 px-2 py-1 safe-area-pb shadow-lg">
      <div className="flex justify-around items-center h-14">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center flex-1 py-1 px-1 rounded-xl transition-all ${
                isActive
                  ? 'text-orange-600 font-bold scale-105'
                  : 'text-slate-500 hover:text-slate-900 font-medium'
              }`
            }
          >
            <item.icon className="w-5 h-5 mb-0.5" />
            <span className="text-[10px] tracking-tight truncate max-w-[64px]">{item.label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
};
