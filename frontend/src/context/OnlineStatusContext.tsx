import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { syncPendingDrafts } from '../utils/offlineSync';

interface OnlineStatusContextType {
  isOnline: boolean;
  wasOffline: boolean;
  pendingSyncCount: number;
  triggerSync: () => Promise<number>;
}

const OnlineStatusContext = createContext<OnlineStatusContextType | undefined>(undefined);

export const OnlineStatusProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== 'undefined' && typeof navigator.onLine === 'boolean' ? navigator.onLine : true
  );
  const [wasOffline, setWasOffline] = useState<boolean>(false);
  const [pendingSyncCount, setPendingSyncCount] = useState<number>(0);

  useEffect(() => {
    const handleOnline = async () => {
      setIsOnline(true);
      setWasOffline(true);

      // Attempt background sync of any drafts saved while offline
      try {
        const synced = await syncPendingDrafts();
        if (synced > 0) {
          console.log(`[PWA Offline Sync] Successfully synced ${synced} offline drafts.`);
        }
      } catch (err) {
        console.warn('[PWA Offline Sync] Background sync error:', err);
      }

      // Hide reconnection indicator after 4 seconds
      const timer = setTimeout(() => {
        setWasOffline(false);
      }, 4000);
      return () => clearTimeout(timer);
    };

    const handleOffline = () => {
      setIsOnline(false);
      setWasOffline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const triggerSync = async (): Promise<number> => {
    if (!isOnline) return 0;
    const count = await syncPendingDrafts();
    setPendingSyncCount(0);
    return count;
  };

  return (
    <OnlineStatusContext.Provider value={{ isOnline, wasOffline, pendingSyncCount, triggerSync }}>
      {children}
    </OnlineStatusContext.Provider>
  );
};

export const useOnlineStatus = (): OnlineStatusContextType => {
  const context = useContext(OnlineStatusContext);
  if (!context) {
    throw new Error('useOnlineStatus must be used within an OnlineStatusProvider');
  }
  return context;
};
