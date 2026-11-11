import React from 'react';
import { useOnlineStatus } from '../context/OnlineStatusContext';
import { useLanguage } from '../context/LanguageContext';
import { WifiOff, Wifi, AlertTriangle } from 'lucide-react';

export const OfflineBanner: React.FC = () => {
  const { isOnline, wasOffline } = useOnlineStatus();
  const { language } = useLanguage();

  if (isOnline && !wasOffline) {
    return null;
  }

  // 1. Reconnected Toast (brief notification after returning online)
  if (isOnline && wasOffline) {
    return (
      <aside
        aria-label="Online status"
        className="bg-emerald-600 text-white text-xs font-semibold py-2 px-4 shadow-md transition-all animate-fade-in flex items-center justify-center space-x-2 z-50 sticky top-0"
      >
        <Wifi className="w-4 h-4 text-emerald-200" />
        <span>
          {language === 'hi'
            ? 'वापस ऑनलाइन आ गए! लाइव डेटा पुनः कनेक्ट हो गया है।'
            : 'Back Online! Live connectivity restored.'}
        </span>
      </aside>
    );
  }

  // 2. Persistent Offline Banner (when disconnected)
  return (
    <aside
      aria-label="Offline status"
      className="bg-amber-600 text-white text-xs font-semibold py-2.5 px-4 shadow-md transition-all flex items-center justify-between z-50 sticky top-0 border-b border-amber-700"
    >
      <div className="flex items-center space-x-2 mx-auto">
        <WifiOff className="w-4 h-4 text-amber-200 shrink-0" />
        <span>
          {language === 'hi'
            ? 'ऑफ़लाइन मोड सक्रिय — सहेजी गई योजनाएं और मार्गदर्शिका उपलब्ध हैं'
            : 'Offline Mode Active — Cached schemes and guidelines available'}
        </span>
      </div>
      <div className="hidden sm:flex items-center space-x-1 text-[11px] bg-amber-700/60 px-2 py-0.5 rounded text-amber-100">
        <AlertTriangle className="w-3 h-3 text-amber-300" />
        <span>PWA Cache</span>
      </div>
    </aside>
  );
};
