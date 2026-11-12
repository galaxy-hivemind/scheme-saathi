import { apiClient } from './client';
import {
  AgentResponse,
  ConversationSummary,
  PersistedConversationResponse,
} from '@/types';
import { MOCK_AGENT_CHAT_RESPONSES } from '../mock/mockData';

export const agentService = {
  async listConversations(): Promise<{ conversations: ConversationSummary[] }> {
    if (apiClient.isMockMode()) {
      return Promise.resolve({ conversations: [] });
    }
    return apiClient.get<{ conversations: ConversationSummary[] }>('/agent/conversations');
  },

  async getConversation(conversationId: string): Promise<PersistedConversationResponse> {
    if (apiClient.isMockMode() || !conversationId) {
      return Promise.resolve({
        conversation_id: conversationId || '',
        active_scheme_code: null,
        workflow_step: 'TALK',
        turns: [],
        state: {},
      });
    }
    return apiClient.get<PersistedConversationResponse>(
      `/agent/conversations/${encodeURIComponent(conversationId)}`
    );
  },

  async sendMessage(
    message: string,
    conversationId?: string,
    language: string = 'auto',
    options?: {
      scheme_id?: string;
      workflow_step?: string;
      form_action?: string;
      form_data?: any;
      expected_version?: number;
      expected_hash?: string;
      idempotency_key?: string;
      official_reference_number?: string;
    }
  ): Promise<AgentResponse> {
    if (apiClient.isMockMode()) {
      const lower = message.toLowerCase();
      let response = MOCK_AGENT_CHAT_RESPONSES.default;
      if (lower.includes('kisan') || lower.includes('farmer') || lower.includes('खेती') || lower.includes('किसान') || lower.includes('शेतकरी')) {
        response = MOCK_AGENT_CHAT_RESPONSES.farmer;
      } else if (lower.includes('scholarship') || lower.includes('छात्र') || lower.includes('student') || lower.includes('शिष्यवृत्ती')) {
        response = MOCK_AGENT_CHAT_RESPONSES.scholarship;
      } else if (lower.includes('doc') || lower.includes('दस्तावेज़') || lower.includes('कागजात') || lower.includes('कागदपत्रे')) {
        response = MOCK_AGENT_CHAT_RESPONSES.documents;
      }

      return Promise.resolve({
        ...response,
        conversation_id: conversationId || `conv-${Date.now()}`,
        spoken_text: response.message,
        detected_language: language === 'auto' ? 'hi' : language,
        workflow_step: options?.workflow_step || 'TALK',
      });
    }

    return apiClient.post<AgentResponse>('/agent/chat', {
      conversation_id: conversationId || null,
      message,
      language,
      scheme_id: options?.scheme_id,
      workflow_step: options?.workflow_step,
      form_action: options?.form_action,
      form_data: options?.form_data,
      expected_version: options?.expected_version,
      expected_hash: options?.expected_hash,
      idempotency_key: options?.idempotency_key,
      official_reference_number: options?.official_reference_number,
    });
  },
};
