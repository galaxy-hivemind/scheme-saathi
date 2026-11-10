import { APIResponse, APIError } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

class APIClient {
  private token: string | null = null;
  private mockMode: boolean = import.meta.env.VITE_USE_MOCK === 'true';

  constructor() {
    // Check localStorage if available in browser environment
    if (typeof window !== 'undefined' && window.localStorage) {
      const savedToken = localStorage.getItem('scheme_saathi_jwt');
      if (savedToken) {
        this.token = savedToken;
      }
      const savedMockPref = localStorage.getItem('scheme_saathi_use_mock');
      if (savedMockPref !== null) {
        this.mockMode = savedMockPref === 'true';
      }
    }
  }

  public setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined' && window.localStorage) {
      if (token) {
        localStorage.setItem('scheme_saathi_jwt', token);
      } else {
        localStorage.removeItem('scheme_saathi_jwt');
      }
    }
  }

  public getToken(): string | null {
    return this.token;
  }

  public isMockMode(): boolean {
    return this.mockMode;
  }

  public setMockMode(enabled: boolean) {
    this.mockMode = enabled;
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem('scheme_saathi_use_mock', String(enabled));
    }
  }

  public async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      const json: APIResponse<T> = await response.json().catch(() => {
        throw {
          code: 'INVALID_JSON_RESPONSE',
          message: 'Received an invalid non-JSON response from the server.',
        } as APIError;
      });

      if (!response.ok || !json.success) {
        const error: APIError = json.error || {
          code: `HTTP_${response.status}`,
          message: response.statusText || 'Request failed.',
        };
        throw error;
      }

      return json.data as T;
    } catch (err: unknown) {
      // If error is already an APIError, rethrow
      if (err && typeof err === 'object' && 'code' in err && 'message' in err) {
        throw err as APIError;
      }
      throw {
        code: 'NETWORK_ERROR',
        message: err instanceof Error ? err.message : 'Unable to connect to the backend server.',
      } as APIError;
    }
  }

  public async get<T>(endpoint: string, params?: Record<string, string | number | undefined>): Promise<T> {
    let url = endpoint;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
      const queryString = searchParams.toString();
      if (queryString) {
        url += (url.includes('?') ? '&' : '?') + queryString;
      }
    }
    return this.request<T>(url, { method: 'GET' });
  }

  public async post<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  public async put<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  public async upload<T>(endpoint: string, formData: FormData): Promise<T> {
    const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });

    const json: APIResponse<T> = await response.json();
    if (!response.ok || !json.success) {
      throw json.error || { code: 'UPLOAD_FAILED', message: 'Failed to upload document' };
    }
    return json.data as T;
  }
}

export const apiClient = new APIClient();
