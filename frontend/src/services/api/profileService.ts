import { apiClient } from './client';
import { UserProfile } from '@/types';
import { MOCK_USER_PROFILE } from '../mock/mockData';

let localProfileState: UserProfile = { ...MOCK_USER_PROFILE };

export const profileService = {
  async getProfile(): Promise<UserProfile> {
    if (apiClient.isMockMode()) {
      return Promise.resolve({ ...localProfileState });
    }
    return apiClient.get<UserProfile>('/profile');
  },

  async createProfile(data: Partial<UserProfile>): Promise<UserProfile> {
    if (apiClient.isMockMode()) {
      localProfileState = {
        ...localProfileState,
        ...data,
        updated_at: new Date().toISOString(),
      };
      return Promise.resolve({ ...localProfileState });
    }
    return apiClient.post<UserProfile>('/profile', data);
  },

  async updateProfile(data: Partial<UserProfile>): Promise<UserProfile> {
    if (apiClient.isMockMode()) {
      localProfileState = {
        ...localProfileState,
        ...data,
        updated_at: new Date().toISOString(),
      };
      return Promise.resolve({ ...localProfileState });
    }
    return apiClient.put<UserProfile>('/profile', data);
  },
};
