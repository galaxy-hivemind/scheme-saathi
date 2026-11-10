import { apiClient } from './client';
import { HealthStatus } from '@/types';

export const healthService = {
  async checkHealth(): Promise<HealthStatus> {
    if (apiClient.isMockMode()) {
      return {
        status: 'ok',
        timestamp: new Date().toISOString(),
        version: '0.1.0-mock',
        database: 'connected (simulated)',
      };
    }
    return apiClient.get<HealthStatus>('/health');
  },
};
