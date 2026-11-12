// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest';
import { ChatPage } from '../ChatPage';
import { LanguageProvider } from '@/context/LanguageContext';
import { agentService } from '@/services/api/agentService';
import { apiClient } from '@/services/api/client';

let mockAuthState = {
  user: { id: 'user-farmer-111', email: 'farmer@example.gov.in' },
  profile: null,
  token: 'test-jwt-token',
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshProfile: vi.fn(),
  updateProfileState: vi.fn(),
};

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => mockAuthState,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('ChatPage Persistent Conversation & Reload Hydration', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeAll(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    Element.prototype.scrollIntoView = vi.fn();

    const store = new Map<string, string>();
    const storageMock: Storage = {
      get length() {
        return store.size;
      },
      clear() {
        store.clear();
      },
      getItem(key: string) {
        return store.has(key) ? store.get(key)! : null;
      },
      key(index: number) {
        return Array.from(store.keys())[index] ?? null;
      },
      removeItem(key: string) {
        store.delete(key);
      },
      setItem(key: string, value: string) {
        store.set(key, String(value));
      },
    };
    Object.defineProperty(window, 'localStorage', {
      value: storageMock,
      configurable: true,
    });
    Object.defineProperty(globalThis, 'localStorage', {
      value: storageMock,
      configurable: true,
    });
  });

  beforeEach(() => {
    window.localStorage.clear();
    apiClient.setMockMode(false);
    mockAuthState = {
      ...mockAuthState,
      user: { id: 'user-farmer-111', email: 'farmer@example.gov.in' },
      token: 'test-jwt-token',
      isLoading: false,
    };
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    vi.restoreAllMocks();
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  it('persists per-user conversationId and hydrates persisted multi-turn history on reload', async () => {
    window.localStorage.setItem('saathi_conv_id_user-farmer-111', 'conv-persisted-42');

    const getConvSpy = vi.spyOn(agentService, 'getConversation').mockResolvedValue({
      conversation_id: 'conv-persisted-42',
      active_scheme_code: 'PM-KISAN',
      workflow_step: 'CHECKLIST',
      language: 'en',
      turns: [
        {
          id: 'u-1',
          role: 'user',
          content: 'Tell me more about PM-KISAN.',
          language: 'en',
        },
        {
          id: 'a-1',
          role: 'assistant',
          content: 'PM-KISAN provides Rs. 6,000 per year to landholding farmer families.',
          spoken_text: 'PM-KISAN provides Rs. 6,000 per year to landholding farmer families.',
          language: 'en',
          response_type: 'benefits_info',
          workflow_step: 'CHECKLIST',
          active_scheme: { scheme_code: 'PM-KISAN', name: 'Pradhan Mantri Kisan Samman Nidhi' },
          tool_calls: ['get_scheme_details'],
        },
      ],
    });

    await act(async () => {
      root.render(
        <MemoryRouter>
          <LanguageProvider>
            <ChatPage />
          </LanguageProvider>
        </MemoryRouter>
      );
    });

    // Allow microtasks from getConversation() promise to flush
    await act(async () => {
      await Promise.resolve();
    });

    expect(getConvSpy).toHaveBeenCalledWith('conv-persisted-42');
    expect(container.textContent).toContain('Tell me more about PM-KISAN.');
    expect(container.textContent).toContain('PM-KISAN provides Rs. 6,000 per year');
    // Voice controls remain mounted alongside persistent chat
    expect(container.querySelector('button[title="Start a new conversation"]')).not.toBeNull();
  });

  it('isolates conversationId per authenticated user and rotates conversationId on New Chat', async () => {
    window.localStorage.setItem('saathi_conv_id_user-farmer-111', 'conv-user-a');
    window.localStorage.setItem('saathi_conv_id_user-student-222', 'conv-user-b');

    const getConvSpy = vi.spyOn(agentService, 'getConversation').mockResolvedValue({
      conversation_id: 'conv-user-a',
      active_scheme_code: null,
      workflow_step: 'TALK',
      turns: [],
    });

    await act(async () => {
      root.render(
        <MemoryRouter>
          <LanguageProvider>
            <ChatPage />
          </LanguageProvider>
        </MemoryRouter>
      );
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(getConvSpy).toHaveBeenCalledWith('conv-user-a');
    expect(getConvSpy).not.toHaveBeenCalledWith('conv-user-b');

    // Click New Chat button -> rotates User A's conversationId without affecting User B's key
    const newChatBtn = container.querySelector('button[title="Start a new conversation"]') as HTMLButtonElement;
    expect(newChatBtn).not.toBeNull();

    await act(async () => {
      newChatBtn.click();
    });

    const newUserAConv = window.localStorage.getItem('saathi_conv_id_user-farmer-111');
    expect(newUserAConv).toBeTruthy();
    expect(newUserAConv).not.toBe('conv-user-a');
    expect(window.localStorage.getItem('saathi_conv_id_user-student-222')).toBe('conv-user-b');
  });

  it('calls backend /agent/conversations endpoints cleanly through agentService', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({
      conversation_id: 'conv-xyz',
      active_scheme_code: 'PM-KISAN',
      workflow_step: 'MATCH',
      turns: [],
    });

    await agentService.getConversation('conv-xyz');
    expect(getSpy).toHaveBeenCalledWith('/agent/conversations/conv-xyz');

    await agentService.listConversations();
    expect(getSpy).toHaveBeenCalledWith('/agent/conversations');
  });
});
