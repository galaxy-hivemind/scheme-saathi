import { apiClient } from './client';

export interface LoginPayload {
  email: string;
  password?: string;
}

export interface RegisterPayload {
  email: string;
  password?: string;
  full_name?: string;
  phone_number?: string;
}

export type RegisterRequest = RegisterPayload;

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user_id: string;
  email: string;
}

export const authService = {
  async register(payload: RegisterPayload): Promise<AuthTokenResponse> {
    if (apiClient.isMockMode()) {
      return {
        access_token: 'mock-registered-jwt-token',
        token_type: 'bearer',
        expires_in_seconds: 604800,
        user_id: 'mock-user-id-01',
        email: payload.email,
      };
    }
    return apiClient.post<AuthTokenResponse>('/auth/register', {
      email: payload.email,
      password: payload.password || 'SecureCitizenPassword123!',
      full_name: payload.full_name || 'Citizen User',
    });
  },

  async login(payload: LoginPayload): Promise<AuthTokenResponse> {
    if (apiClient.isMockMode()) {
      return {
        access_token: 'mock-logged-in-jwt-token',
        token_type: 'bearer',
        expires_in_seconds: 604800,
        user_id: 'mock-user-id-01',
        email: payload.email,
      };
    }
    return apiClient.post<AuthTokenResponse>('/auth/login', {
      email: payload.email,
      password: payload.password || 'SecureCitizenPassword123!',
    });
  },
};
