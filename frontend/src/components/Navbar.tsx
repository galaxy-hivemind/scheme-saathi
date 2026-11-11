import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import {
  Sparkles,
  Bell,
  Globe,
  LogOut,
  User as UserIcon,
  Menu,
  X,
  FileCheck2,
  FileText,
  Clock,
  Compass,
} from 'lucide-react';

interface NavbarProps {
  onOpenNotifications?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenNotifications }) => {
  const { language, toggleLanguage, t } = useLanguage();
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  useEffect(() => {
    if (isAuthenticated) {
      api.notifications
        .getUnreadCount()
        .then((count) => setUnreadCount(count))
        .catch(() => setUnreadCount(0));

      const interval = setInterval(() => {
        api.notifications
          .getUnreadCount()
          .then((count) => setUnreadCount(count))
          .catch(() => {});
      }, 30000); // 30s poll

      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-600 to-green-600 flex items-center justify-center text-white shadow-md shadow-orange-500/20 group-hover:scale-105 transition-transform">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-orange-600 to-green-700 bg-clip-text text-transparent">
                  {language === 'hi' ? 'योजना साथी' : 'Scheme Saathi'}
                </span>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-1.5 py-0.5 bg-orange-100 text-orange-800 rounded">
                  2026
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium hidden sm:block">
                {language === 'hi' ? 'सरकारी कल्याणकारी योजना सहायक' : 'Government Welfare Scheme Assistant'}
              </p>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          {isAuthenticated && (
            <nav className="hidden md:flex items-center space-x-1">
              <Link
                to="/"
                className="px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:text-orange-600 hover:bg-orange-50 transition-colors flex items-center space-x-1.5"
              >
                <Sparkles className="w-4 h-4 text-orange-500" />
                <span>{t('nav.chat')}</span>
              </Link>
              <Link
                to="/schemes"
                className="px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:text-orange-600 hover:bg-orange-50 transition-colors flex items-center space-x-1.5"
              >
                <Compass className="w-4 h-4 text-blue-500" />
                <span>{t('nav.schemes')}</span>
              </Link>
              <Link
                to="/documents"
                className="px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:text-orange-600 hover:bg-orange-50 transition-colors flex items-center space-x-1.5"
              >
                <FileCheck2 className="w-4 h-4 text-emerald-500" />
                <span>{t('nav.documents')}</span>
              </Link>
              <Link
                to="/applications"
                className="px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:text-orange-600 hover:bg-orange-50 transition-colors flex items-center space-x-1.5"
              >
                <FileText className="w-4 h-4 text-purple-500" />
                <span>{t('nav.applications')}</span>
              </Link>
              <Link
                to="/tracking"
                className="px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:text-orange-600 hover:bg-orange-50 transition-colors flex items-center space-x-1.5"
              >
                <Clock className="w-4 h-4 text-amber-500" />
                <span>{t('nav.tracking')}</span>
              </Link>
            </nav>
          )}

          {/* Action Buttons: Language Toggle, Notification Bell, User Profile */}
          <div className="flex items-center space-x-2 sm:space-x-3">
            {/* Language Toggle Button */}
            <button
              onClick={toggleLanguage}
              className="px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-700 flex items-center space-x-1.5 transition-colors shadow-sm"
              title="Toggle Hindi / English"
            >
              <Globe className="w-3.5 h-3.5 text-orange-600" />
              <span>{language === 'hi' ? 'English' : 'हिन्दी'}</span>
            </button>

            {/* Notification Bell */}
            {isAuthenticated && (
              <button
                onClick={onOpenNotifications || (() => navigate('/tracking'))}
                className="relative p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                title={t('nav.notifications')}
              >
                <Bell className="w-5 h-5" />
                {unreadCount > 0 && (
                  <span className="absolute top-1 right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-rose-600 rounded-full shadow-sm animate-pulse">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>
            )}

            {/* Auth Buttons / User Avatar */}
            {isAuthenticated ? (
              <div className="flex items-center space-x-2">
                <Link
                  to="/profile"
                  className="flex items-center space-x-2 p-1.5 rounded-lg hover:bg-slate-100 transition-colors text-slate-700"
                >
                  <div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center text-slate-700 font-semibold text-xs">
                    {user?.profile?.full_name?.charAt(0) || user?.email?.charAt(0) || 'U'}
                  </div>
                  <span className="text-xs font-medium text-slate-700 hidden lg:inline max-w-[120px] truncate">
                    {user?.profile?.full_name || user?.email}
                  </span>
                </Link>

                <button
                  onClick={logout}
                  className="p-2 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                  title={t('nav.logout')}
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <Link
                  to="/login"
                  className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 hover:bg-slate-100 transition-colors"
                >
                  {t('nav.login')}
                </Link>
                <Link
                  to="/register"
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-orange-600 hover:bg-orange-700 text-white shadow-sm transition-colors"
                >
                  {t('nav.register')}
                </Link>
              </div>
            )}

            {/* Mobile Menu Toggle Button */}
            {isAuthenticated && (
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              >
                {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Drawer Navigation */}
      {isAuthenticated && isMobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white px-4 pt-2 pb-4 space-y-1 shadow-lg">
          <Link
            to="/"
            onClick={() => setIsMobileMenuOpen(false)}
            className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-orange-50 hover:text-orange-600"
          >
            <Sparkles className="w-5 h-5 text-orange-500" />
            <span>{t('nav.chat')}</span>
          </Link>
          <Link
            to="/schemes"
            onClick={() => setIsMobileMenuOpen(false)}
            className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-orange-50 hover:text-orange-600"
          >
            <Compass className="w-5 h-5 text-blue-500" />
            <span>{t('nav.schemes')}</span>
          </Link>
          <Link
            to="/documents"
            onClick={() => setIsMobileMenuOpen(false)}
            className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-orange-50 hover:text-orange-600"
          >
            <FileCheck2 className="w-5 h-5 text-emerald-500" />
            <span>{t('nav.documents')}</span>
          </Link>
          <Link
            to="/applications"
            onClick={() => setIsMobileMenuOpen(false)}
            className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-orange-50 hover:text-orange-600"
          >
            <FileText className="w-5 h-5 text-purple-500" />
            <span>{t('nav.applications')}</span>
          </Link>
          <Link
            to="/tracking"
            onClick={() => setIsMobileMenuOpen(false)}
            className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-orange-50 hover:text-orange-600"
          >
            <Clock className="w-5 h-5 text-amber-500" />
            <span>{t('nav.tracking')}</span>
          </Link>
          <Link
            to="/profile"
            onClick={() => setIsMobileMenuOpen(false)}
            className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-orange-50 hover:text-orange-600"
          >
            <UserIcon className="w-5 h-5 text-slate-500" />
            <span>{t('nav.profile')}</span>
          </Link>
        </div>
      )}
    </header>
  );
};
