import { apiClient } from './client';
import { AgentResponse } from '@/types';
import { MOCK_AGENT_CHAT_RESPONSES } from '../mock/mockData';

export const agentService = {
  async sendMessage(message: string, conversationId?: string, language: 'hi' | 'en' = 'hi'): Promise<AgentResponse> {
    if (apiClient.isMockMode()) {
      const lower = message.toLowerCase();
      let response = MOCK_AGENT_CHAT_RESPONSES.default;
      if (lower.includes('kisan') || lower.includes('farmer') || lower.includes('खेती') || lower.includes('किसान')) {
        response = MOCK_AGENT_CHAT_RESPONSES.farmer;
      } else if (lower.includes('scholarship') || lower.includes('छात्र') || lower.includes('student')) {
        response = MOCK_AGENT_CHAT_RESPONSES.scholarship;
      } else if (lower.includes('doc') || lower.includes('दस्तावेज़') || lower.includes('कागजात')) {
        response = MOCK_AGENT_CHAT_RESPONSES.documents;
      }

      return Promise.resolve({
        ...response,
        conversation_id: conversationId || `conv-${Date.now()}`,
      });
    }

    return apiClient.post<AgentResponse>('/agent/chat', {
      conversation_id: conversationId || null,
      message,
      language,
    });
  },
};
