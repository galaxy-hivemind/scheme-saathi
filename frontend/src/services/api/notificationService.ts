import { apiClient } from './client';
import { Notification } from '@/types';
import { MOCK_NOTIFICATIONS } from '../mock/mockData';

let localNotifications = [...MOCK_NOTIFICATIONS];

export const notificationService = {
  async getNotifications(): Promise<Notification[]> {
    if (apiClient.isMockMode()) {
      return Promise.resolve([...localNotifications]);
    }
    return apiClient.get<Notification[]>('/notifications');
  },

  async markAsRead(id: string): Promise<void> {
    if (apiClient.isMockMode()) {
      const item = localNotifications.find((n) => n.id === id);
      if (item) {
        item.read_at = new Date().toISOString();
      }
      return Promise.resolve();
    }
    return apiClient.put<void>(`/notifications/${id}/read`);
  },
};
