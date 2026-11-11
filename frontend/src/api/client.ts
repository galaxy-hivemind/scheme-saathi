import axios, { AxiosError } from 'axios';
import {
  User,
  UserProfile,
  BeneficiaryProfile,
  Scheme,
  SchemeSummary,
  EligibilityResult,
  ChatConversation,
  ChatMessage,
  PendingAction,
  CitizenDocument,
  DocumentChecklistResponse,
  ApplicationDraft,
  ApplicationTimelineResponse,
  NotificationListResponse,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach JWT bearer token if present
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('scheme_saathi_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle token expiration
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('scheme_saathi_token');
      // Redirect to login if not already there
      if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ── Typed API Service Methods ───────────────────────────────────────────────

export const api = {
  // ── Authentication ──
  auth: {
    login: async (email: string, password: string) => {
      const res = await apiClient.post('/auth/login', { email, password });
      return res.data?.data;
    },
    register: async (payload: { email: string; password: string; full_name: string; preferred_language?: string }) => {
      const res = await apiClient.post('/auth/register', payload);
      return res.data?.data;
    },
    getMe: async (): Promise<User> => {
      const res = await apiClient.get('/auth/me');
      return res.data?.data;
    },
  },

  // ── Citizen Profile ──
  profile: {
    get: async (): Promise<UserProfile> => {
      const res = await apiClient.get('/profile');
      return res.data?.data;
    },
    update: async (data: Partial<UserProfile>): Promise<UserProfile> => {
      const res = await apiClient.put('/profile', data);
      return res.data?.data;
    },
  },

  // ── Family Beneficiaries ──
  beneficiaries: {
    list: async (): Promise<BeneficiaryProfile[]> => {
      const res = await apiClient.get('/beneficiaries');
      return res.data?.data?.items || [];
    },
    create: async (data: Partial<BeneficiaryProfile>): Promise<BeneficiaryProfile> => {
      const res = await apiClient.post('/beneficiaries', data);
      return res.data?.data;
    },
    update: async (id: string, data: Partial<BeneficiaryProfile>): Promise<BeneficiaryProfile> => {
      const res = await apiClient.put(`/beneficiaries/${id}`, data);
      return res.data?.data;
    },
    delete: async (id: string) => {
      const res = await apiClient.delete(`/beneficiaries/${id}`);
      return res.data;
    },
  },

  // ── Schemes Catalogue ──
  schemes: {
    list: async (params?: { q?: string; category?: string; page?: number; limit?: number }): Promise<{ items: SchemeSummary[]; total: number }> => {
      const res = await apiClient.get('/schemes', { params });
      return res.data?.data;
    },
    get: async (id: string): Promise<Scheme> => {
      const res = await apiClient.get(`/schemes/${id}`);
      return res.data?.data;
    },
  },

  // ── Eligibility Engine ──
  eligibility: {
    evaluate: async (schemeId: string, beneficiaryId?: string | null, profileOverride?: Record<string, any>): Promise<EligibilityResult> => {
      const res = await apiClient.post(`/eligibility/evaluate/${schemeId}`, {
        beneficiary_id: beneficiaryId,
        profile_override: profileOverride,
      });
      return res.data?.data;
    },
    evaluateAll: async (beneficiaryId?: string | null, category?: string): Promise<EligibilityResult[]> => {
      const res = await apiClient.post('/eligibility/evaluate-all', {
        beneficiary_id: beneficiaryId,
        category,
      });
      return res.data?.data?.results || [];
    },
  },

  // ── Conversational Agent ──
  agent: {
    chat: async (message: string, conversationId?: string | null): Promise<{
      conversation_id: string;
      message: string;
      pending_action?: PendingAction | null;
      intent?: string;
    }> => {
      const res = await apiClient.post('/agent/chat', {
        message,
        conversation_id: conversationId,
      });
      return res.data?.data;
    },
    listConversations: async (): Promise<{ items: ChatConversation[]; total: number }> => {
      const res = await apiClient.get('/agent/conversations');
      return res.data?.data;
    },
    getConversation: async (id: string): Promise<{ conversation: ChatConversation; messages: ChatMessage[] }> => {
      const res = await apiClient.get(`/agent/conversations/${id}`);
      return res.data?.data;
    },
    confirmAction: async (actionId: string): Promise<any> => {
      const res = await apiClient.post(`/agent/actions/${actionId}/confirm`);
      return res.data?.data;
    },
    cancelAction: async (actionId: string): Promise<any> => {
      const res = await apiClient.post(`/agent/actions/${actionId}/cancel`);
      return res.data?.data;
    },
  },

  // ── Document Checklist & Secure Upload ──
  documents: {
    getChecklist: async (schemeId: string, beneficiaryId?: string | null): Promise<DocumentChecklistResponse> => {
      const res = await apiClient.get(`/documents/checklist/${schemeId}`, {
        params: beneficiaryId ? { beneficiary_id: beneficiaryId } : {},
      });
      return res.data?.data;
    },
    list: async (documentType?: string, beneficiaryId?: string | null): Promise<{ items: CitizenDocument[]; total: number }> => {
      const res = await apiClient.get('/documents', {
        params: {
          document_type: documentType,
          beneficiary_id: beneficiaryId,
        },
      });
      return res.data?.data;
    },
    upload: async (file: File, documentType: string, beneficiaryId?: string | null): Promise<CitizenDocument> => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_type', documentType);
      if (beneficiaryId) {
        formData.append('beneficiary_id', beneficiaryId);
      }
      const res = await apiClient.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data?.data;
    },
    delete: async (id: string) => {
      const res = await apiClient.delete(`/documents/${id}`);
      return res.data;
    },
  },

  // ── Application Drafts & Portal Handoff ──
  applications: {
    createDraft: async (schemeId: string, beneficiaryId?: string | null, notes?: string): Promise<ApplicationDraft> => {
      const res = await apiClient.post('/applications/draft', {
        scheme_id: schemeId,
        beneficiary_id: beneficiaryId,
        notes,
      });
      return res.data?.data;
    },
    list: async (status?: string, schemeId?: string): Promise<{ items: ApplicationDraft[]; total: number }> => {
      const res = await apiClient.get('/applications', {
        params: { status, scheme_id: schemeId },
      });
      return res.data?.data;
    },
    get: async (id: string): Promise<ApplicationDraft> => {
      const res = await apiClient.get(`/applications/${id}`);
      return res.data?.data;
    },
    update: async (id: string, notes?: string, prefilledData?: Record<string, any>): Promise<ApplicationDraft> => {
      const res = await apiClient.put(`/applications/${id}`, {
        notes,
        prefilled_data: prefilledData,
      });
      return res.data?.data;
    },
    submit: async (id: string, externalReferenceNumber: string, notes?: string): Promise<ApplicationDraft> => {
      const res = await apiClient.post(`/applications/${id}/submit`, {
        external_reference_number: externalReferenceNumber,
        notes,
      });
      return res.data?.data;
    },
    delete: async (id: string) => {
      const res = await apiClient.delete(`/applications/${id}`);
      return res.data;
    },
  },

  // ── Tracking Timeline ──
  tracking: {
    getTimeline: async (applicationId: string): Promise<ApplicationTimelineResponse> => {
      const res = await apiClient.get(`/tracking/${applicationId}/timeline`);
      return res.data;
    },
    updateStatus: async (applicationId: string, status: string, notes?: string, sourceReference?: string): Promise<ApplicationTimelineResponse> => {
      const res = await apiClient.post(`/tracking/${applicationId}/status`, {
        status,
        notes,
        source_reference: sourceReference,
      });
      return res.data;
    },
    syncStatus: async (applicationId: string): Promise<ApplicationTimelineResponse> => {
      const res = await apiClient.post(`/tracking/${applicationId}/sync`);
      return res.data;
    },
  },

  // ── Notifications ──
  notifications: {
    list: async (isRead?: boolean, limit: number = 50, offset: number = 0): Promise<NotificationListResponse> => {
      const res = await apiClient.get('/notifications', {
        params: { is_read: isRead, limit, offset },
      });
      return res.data;
    },
    getUnreadCount: async (): Promise<number> => {
      const res = await apiClient.get('/notifications/unread-count');
      return res.data?.unread_count || 0;
    },
    markAsRead: async (id: string) => {
      const res = await apiClient.put(`/notifications/${id}/read`);
      return res.data;
    },
    markAllAsRead: async () => {
      const res = await apiClient.put('/notifications/read-all');
      return res.data;
    },
  },
};
