import { apiClient } from './client';
import { Scheme } from '@/types';
import { MOCK_SCHEMES } from '../mock/mockData';

export interface SchemeFilterParams {
  q?: string;
  category?: string;
  page?: number;
  limit?: number;
  include_pending?: boolean;
}

export const schemeService = {
  async getSchemes(params?: SchemeFilterParams): Promise<Scheme[]> {
    if (apiClient.isMockMode()) {
      let filtered = [...MOCK_SCHEMES];
      if (params?.q) {
        const query = params.q.toLowerCase();
        filtered = filtered.filter(
          (s) =>
            s.name.toLowerCase().includes(query) ||
            s.description.toLowerCase().includes(query) ||
            s.benefits.toLowerCase().includes(query)
        );
      }
      if (params?.category) {
        filtered = filtered.filter((s) => s.category === params.category);
      }
      return Promise.resolve(filtered);
    }
    const res = await apiClient.get<Scheme[] | { items: Scheme[] }>('/schemes', {
      include_pending: true,
      limit: 50,
      ...params,
    } as Record<string, string | number | boolean | undefined>);
    if (Array.isArray(res)) {
      return res;
    }
    if (res && Array.isArray((res as { items?: Scheme[] }).items)) {
      return (res as { items: Scheme[] }).items;
    }
    return [];
  },

  async getSchemeById(schemeId: string): Promise<Scheme> {
    if (apiClient.isMockMode()) {
      const scheme = MOCK_SCHEMES.find((s) => s.id === schemeId);
      if (!scheme) {
        throw { code: 'NOT_FOUND', message: `Scheme with ID '${schemeId}' not found.` };
      }
      return Promise.resolve(scheme);
    }
    return apiClient.get<Scheme>(`/schemes/${schemeId}?include_pending=true`);
  },
};
