import React, { useState, useEffect } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Download, Smartphone, X } from 'lucide-react';

export const InstallPwaPrompt: React.FC = () => {
  const { language } = useLanguage();
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isVisible, setIsVisible] = useState<boolean>(false);

  useEffect(() => {
    // Check if dismissed in this session
    const isDismissed = sessionStorage.getItem('scheme_saathi_install_dismissed');
    if (isDismissed) return;

    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setIsVisible(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
    };
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setIsVisible(false);
      setDeferredPrompt(null);
    }
  };

  const handleDismiss = () => {
    setIsVisible(false);
    sessionStorage.setItem('scheme_saathi_install_dismissed', 'true');
  };

  if (!isVisible || !deferredPrompt) {
    return null;
  }

  return (
    <div
      role="region"
      aria-label="PWA install banner"
      className="fixed bottom-20 left-4 right-4 sm:left-auto sm:right-6 sm:bottom-6 sm:max-w-sm z-40 bg-white border border-slate-200/90 rounded-2xl shadow-xl p-3.5 sm:p-4 flex items-center justify-between space-x-3 animate-slide-up"
    >
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-600 to-green-600 flex items-center justify-center text-white shadow-md shadow-orange-500/20 shrink-0">
          <Smartphone className="w-5 h-5" />
        </div>
        <div>
          <h4 className="text-xs font-bold text-slate-900 leading-snug">
            {language === 'hi' ? 'योजना साथी ऐप इंस्टॉल करें' : 'Install Scheme Saathi App'}
          </h4>
          <p className="text-[11px] text-slate-500">
            {language === 'hi'
              ? 'बिना इंटरनेट के भी योजनाएं देखें'
              : 'Browse schemes faster and offline'}
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-1 shrink-0">
        <button
          onClick={handleInstallClick}
          className="px-3 py-1.5 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow-sm transition-colors flex items-center space-x-1"
        >
          <Download className="w-3.5 h-3.5" />
          <span>{language === 'hi' ? 'इंस्टॉल' : 'Install'}</span>
        </button>

        <button
          onClick={handleDismiss}
          className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg transition-colors"
          title="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
