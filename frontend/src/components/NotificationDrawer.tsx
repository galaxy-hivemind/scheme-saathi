import React, { useState, useEffect } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { api } from '../api/client';
import { NotificationItem } from '../types';
import { X, Bell, CheckCheck, Clock, AlertTriangle, ShieldCheck, Info } from 'lucide-react';

interface NotificationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NotificationDrawer: React.FC<NotificationDrawerProps> = ({ isOpen, onClose }) => {
  const { t } = useLanguage();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchNotifications = async () => {
    setIsLoading(true);
    try {
      const res = await api.notifications.list();
      setNotifications(res.items || []);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen]);

  const handleMarkAsRead = async (id: string) => {
    try {
      await api.notifications.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n))
      );
    } catch (err) {
      console.error('Failed to mark read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.notifications.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Failed to mark all read:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col transform transition-transform animate-slide-left">
        {/* Header */}
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2">
            <Bell className="w-5 h-5 text-orange-600" />
            <h2 className="font-bold text-base text-slate-800">{t('notifications.title')}</h2>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleMarkAllRead}
              className="p-1.5 text-xs text-orange-600 hover:text-orange-700 hover:bg-orange-50 rounded-lg flex items-center space-x-1 font-medium transition-colors"
              title={t('notifications.mark_all_read')}
            >
              <CheckCheck className="w-4 h-4" />
              <span className="hidden sm:inline">{t('notifications.mark_all_read')}</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {isLoading ? (
            <div className="py-12 text-center text-sm text-slate-500">सूचनाएं लोड हो रही हैं... / Loading...</div>
          ) : notifications.length === 0 ? (
            <div className="py-16 text-center">
              <Bell className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-sm font-medium text-slate-600">{t('notifications.empty')}</p>
            </div>
          ) : (
            notifications.map((item) => (
              <div
                key={item.id}
                onClick={() => !item.is_read && handleMarkAsRead(item.id)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                  item.is_read
                    ? 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                    : 'bg-orange-50/60 border-orange-200 text-slate-900 shadow-sm hover:border-orange-300'
                }`}
              >
                <div className="flex items-start justify-between mb-1.5">
                  <div className="flex items-center space-x-2">
                    {item.priority === 'HIGH' || item.priority === 'URGENT' ? (
                      <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
                    ) : item.notification_type === 'status_update' ? (
                      <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                    ) : (
                      <Info className="w-4 h-4 text-blue-500 shrink-0" />
                    )}
                    <h3 className="font-semibold text-xs tracking-tight">{item.title}</h3>
                  </div>
                  {!item.is_read && (
                    <span className="w-2 h-2 rounded-full bg-orange-600 shrink-0" title="Unread" />
                  )}
                </div>
                <p className="text-xs leading-relaxed mb-2 text-slate-600">{item.message}</p>
                <div className="flex items-center justify-between text-[10px] text-slate-400">
                  <span className="flex items-center space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
                  </span>
                  <span className="uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                    {item.priority}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
