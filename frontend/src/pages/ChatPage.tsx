import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { agentService } from '@/services/api/agentService';
import {
  ChatMessage,
  ChatResponseType,
  PersistedConversationTurn,
  DocumentRequirement,
  ApplicationGuideData,
  BenefitsInfoData,
  StatusTrackingData,
} from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { useAuth } from '@/context/AuthContext';
import { useVoiceAssistant, AssistantLanguage } from '@/hooks/useVoiceAssistant';
import { Button } from '@/components/common/Button';
import { Card, CardContent } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { WorkflowStepper, WorkflowStage } from '@/components/chat/WorkflowStepper';
import {
  InteractiveChecklistWidget,
  ChecklistPayload,
} from '@/components/chat/InteractiveChecklistWidget';
import {
  PreFilledFormWidget,
  FormDraftPayload,
} from '@/components/chat/PreFilledFormWidget';
import {
  HandoffConfirmationWidget,
  ConfirmationPayload,
} from '@/components/chat/HandoffConfirmationWidget';
import {
  Send,
  Sparkles,
  User,
  FileText,
  ArrowRight,
  Bot,
  ShieldCheck,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Play,
  Pause,
  Languages,
  AlertTriangle,
  StopCircle,
  ExternalLink,
  CheckCircle2,
  Building2,
  Coins,
  RotateCcw,
} from 'lucide-react';

const getConversationStorageKey = (userId?: string | null): string =>
  userId ? `saathi_conv_id_${userId}` : 'saathi_conv_id_anon';

const generateConversationId = (): string =>
  `conv-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

const readOrCreateConversationId = (userId?: string | null): string => {
  const key = getConversationStorageKey(userId);
  if (typeof window !== 'undefined' && window.localStorage) {
    const existing = window.localStorage.getItem(key);
    if (existing && existing.trim()) {
      return existing;
    }
    const created = generateConversationId();
    window.localStorage.setItem(key, created);
    return created;
  }
  return generateConversationId();
};

export const ChatPage: React.FC = () => {
  const { t, language } = useLanguage();
  const { user, token, isLoading: authLoading } = useAuth();

  const getInitialMessage = (lang: string): ChatMessage => {
    if (lang === 'en') {
      return {
        id: 'init-01',
        conversation_id: 'conv-init',
        role: 'assistant',
        message_content:
          'Hello! I am your Scheme Saathi. You can ask me in English, Hindi, or Marathi about government welfare schemes, personalized eligibility, required documents, and application steps.',
        spoken_text:
          'Hello! I am your Scheme Saathi. You can ask me in English, Hindi, or Marathi about government welfare schemes, personalized eligibility, and required documents.',
        detected_language: 'en',
        response_type: 'text',
        suggested_followups: [
          'What is PM-KISAN? Explain its eligibility and required documents.',
          'Which documents do I need for Kisan Credit Card?',
          'Am I eligible for Ayushman Bharat?',
          'Show schemes for farmers in Maharashtra',
        ],
        created_at: new Date().toISOString(),
      };
    }
    if (lang === 'hi') {
      return {
        id: 'init-01',
        conversation_id: 'conv-init',
        role: 'assistant',
        message_content:
          'नमस्ते! मैं आपका योजना साथी हूँ। आप मुझसे हिंदी, मराठी या अंग्रेजी में सरकारी योजनाओं की जानकारी, पात्रता, आवश्यक दस्तावेज़ और आवेदन प्रक्रिया के बारे में पूछ सकते हैं।',
        spoken_text:
          'नमस्ते! मैं आपका योजना साथी हूँ। आप मुझसे सरकारी योजनाओं की जानकारी, पात्रता और आवश्यक दस्तावेज पूछ सकते हैं।',
        detected_language: 'hi',
        response_type: 'text',
        suggested_followups: [
          'पीएम-किसान योजना क्या है? इसकी पात्रता और आवश्यक दस्तावेज़ समझाइए।',
          'किसान क्रेडिट कार्ड के लिए कौन से दस्तावेज चाहिए?',
          'क्या मैं आयुष्मान भारत योजना के लिए पात्र हूँ?',
          'महाराष्ट्र के किसानों के लिए सरकारी योजनाएं बताएं',
        ],
        created_at: new Date().toISOString(),
      };
    }
    return {
      id: 'init-01',
      conversation_id: 'conv-init',
      role: 'assistant',
      message_content:
        'नमस्ते! मी तुमचा योजना साथी आहे. आपण मराठी, हिंदी किंवा इंग्रजीत शासकीय योजनांची माहिती, आपली वैयक्तिक पात्रता, आवश्यक कागदपत्रे आणि अर्ज प्रक्रियेबद्दल विचारू शकता.',
      spoken_text:
        'नमस्ते! मी तुमचा योजना साथी आहे. आपण मराठी, हिंदी किंवा इंग्रजीत शासकीय योजना, पात्रता आणि कागदपत्रांबद्दल विचारू शकता.',
      detected_language: 'mr',
      response_type: 'text',
      suggested_followups: [
        'पीएम-किसान योजना काय आहे? तिची पात्रता आणि आवश्यक कागदपत्रे समजावून सांगा.',
        'किसान क्रेडिट कार्डसाठी कोणती कागदपत्रे लागतील?',
        'मी आयुष्यमान भारत योजनेसाठी पात्र आहे का?',
        'महाराष्ट्रातील शेतकऱ्यांसाठी योजना सांगा',
      ],
      created_at: new Date().toISOString(),
    };
  };

  const [conversationId, setConversationId] = useState<string>(() =>
    readOrCreateConversationId(user?.id)
  );
  const [selectedLanguage, setSelectedLanguage] = useState<AssistantLanguage>('auto');
  const [messages, setMessages] = useState<ChatMessage[]>(() => [getInitialMessage(language)]);

  // Synchronize initial welcome message if user switches header language before starting chat
  useEffect(() => {
    setMessages((prev) => {
      if (prev.length === 1 && prev[0].id === 'init-01') {
        return [getInitialMessage(language)];
      }
      return prev;
    });
  }, [language]);

  const [input, setInput] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [workflowStep, setWorkflowStep] = useState<WorkflowStage | string>('TALK');
  const [activeScheme, setActiveScheme] = useState<{
    scheme_code?: string;
    scheme_name?: string;
    name?: string;
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastOwnerKeyRef = useRef<string | null>(null);
  const hydratedConvRef = useRef<string | null>(null);

  // Persist per-user conversation ID and restore full persisted turns & state across reloads
  useEffect(() => {
    if (authLoading) return;

    const ownerKey = user?.id || 'anon';
    const resolvedConvId = readOrCreateConversationId(user?.id);

    if (lastOwnerKeyRef.current !== null && lastOwnerKeyRef.current !== ownerKey) {
      // Clear local message state when switching authenticated accounts so no citizen context bleeds over
      setMessages([getInitialMessage(language)]);
      setWorkflowStep('TALK');
      setActiveScheme(null);
      hydratedConvRef.current = null;
    }
    lastOwnerKeyRef.current = ownerKey;

    setConversationId((prev) => (prev === resolvedConvId ? prev : resolvedConvId));

    if (!token || !user?.id || hydratedConvRef.current === resolvedConvId) {
      return;
    }

    let cancelled = false;

    agentService
      .getConversation(resolvedConvId)
      .then((persisted) => {
        if (cancelled) return;
        hydratedConvRef.current = resolvedConvId;
        const turns: PersistedConversationTurn[] = Array.isArray(persisted?.turns)
          ? persisted.turns
          : [];
        if (turns.length === 0) return;

        const restoredMessages: ChatMessage[] = turns.map((turn, idx) => ({
          id: turn.id || `restored-${idx}`,
          conversation_id: persisted.conversation_id || resolvedConvId,
          role: turn.role,
          message_content: turn.content || '',
          spoken_text: turn.spoken_text || turn.content || '',
          detected_language: turn.language,
          response_type: (turn.response_type as ChatResponseType) || 'text',
          data: turn.data,
          suggested_followups: turn.suggested_followups || [],
          engine_mode: (turn.engine_mode as 'deterministic' | 'gemini_grounded') || 'deterministic',
          workflow_step: turn.workflow_step,
          active_scheme: turn.active_scheme,
          eligibility_summary: turn.eligibility_summary,
          checklist_data: turn.checklist_data,
          form_draft_data: turn.form_draft_data,
          confirmation_data: turn.confirmation_data,
          tool_calls_used: turn.tool_calls || [],
          created_at: turn.created_at || new Date().toISOString(),
        }));

        setMessages((prev) => {
          const hasUnsavedUserMsgs = prev.some((m) => m.id !== 'init-01');
          return hasUnsavedUserMsgs ? prev : restoredMessages;
        });

        if (persisted.workflow_step) {
          setWorkflowStep(persisted.workflow_step);
        }
        const lastActive = [...turns].reverse().find((t) => t.active_scheme)?.active_scheme;
        if (lastActive) {
          setActiveScheme(lastActive);
        } else if (persisted.active_scheme_code) {
          setActiveScheme({ scheme_code: persisted.active_scheme_code });
        }
      })
      .catch((err) => {
        console.debug('Conversation hydration skipped cleanly:', err);
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, user?.id, token]);

  // Voice Assistant Hook (Speech-to-Text & Text-to-Speech)
  const {
    isListening,
    isSttSupported,
    transcript,
    interimTranscript,
    sttError,
    startListening,
    stopListening,
    resetTranscript,
    isSpeaking,
    isPaused,
    speakingMessageId,
    activeVoiceNotice,
    speak,
    pauseSpeaking,
    resumeSpeaking,
    stopSpeaking,
  } = useVoiceAssistant();

  // Sync spoken transcript into input box so user can see, review and edit before sending
  useEffect(() => {
    if (transcript) {
      setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
      resetTranscript();
    }
  }, [transcript, resetTranscript]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, isListening]);

  // Restore workflow stage and active scheme from conversation message history
  useEffect(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.workflow_step) {
        setWorkflowStep(m.workflow_step);
        if (m.active_scheme) {
          setActiveScheme(m.active_scheme);
        }
        break;
      }
    }
  }, [messages]);

  const handleSend = async (
    messageText: string,
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
  ) => {
    const query = messageText.trim();
    if (!query || loading) return;

    if (isListening) {
      stopListening();
    }

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      conversation_id: conversationId,
      role: 'user',
      message_content: query,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await agentService.sendMessage(query, conversationId, selectedLanguage, {
        scheme_id: options?.scheme_id || activeScheme?.scheme_code,
        workflow_step: options?.workflow_step || (workflowStep as string),
        form_action: options?.form_action,
        form_data: options?.form_data,
        expected_version: options?.expected_version,
        expected_hash: options?.expected_hash,
        idempotency_key: options?.idempotency_key,
        official_reference_number: options?.official_reference_number,
      });

      // Update workflow stage and active scheme if provided by the backend
      if (response.workflow_step) {
        setWorkflowStep(response.workflow_step);
      }
      if (response.active_scheme) {
        setActiveScheme(response.active_scheme);
      }

      const assistantMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        conversation_id: response.conversation_id,
        role: 'assistant',
        message_content: response.message,
        spoken_text: response.spoken_text || response.message,
        detected_language: response.detected_language || 'mr',
        response_type: response.response_type,
        data: response.data,
        suggested_followups: response.suggested_followups || [],
        engine_mode: response.engine_mode || 'deterministic',
        workflow_step: response.workflow_step,
        active_scheme: response.active_scheme,
        eligibility_summary: response.eligibility_summary,
        checklist_data: response.checklist_data,
        form_draft_data: response.form_draft_data,
        confirmation_data: response.confirmation_data,
        tool_calls_used: response.tool_calls_used || [],
        created_at: new Date().toISOString(),
      };

      if (response.conversation_id && typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(getConversationStorageKey(user?.id), response.conversation_id);
        if (response.conversation_id !== conversationId) {
          hydratedConvRef.current = response.conversation_id;
          setConversationId(response.conversation_id);
        }
      }

      setMessages((prev) => [...prev, assistantMsg]);

      // Automatically speak complete conversational response if speech recognition was used
      if (isSttSupported) {
        const textToSpeak = assistantMsg.spoken_text || assistantMsg.message_content;
        speak(textToSpeak, assistantMsg.detected_language || 'mr', assistantMsg.id);
      }
    } catch (err) {
      console.error('Chat error:', err);
      const errLang = selectedLanguage === 'auto' ? language : selectedLanguage;
      const errText =
        errLang === 'en'
          ? 'Sorry, there was a problem connecting to the server. Please try again.'
          : errLang === 'mr'
          ? 'माफ करा, सर्व्हरशी संपर्क साधताना समस्या आली. कृपया पुन्हा प्रयत्न करा.'
          : 'क्षमा करें, अनुरोध संसाधित करने में समस्या हुई। कृपया पुनः प्रयास करें।';
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        conversation_id: conversationId,
        role: 'assistant',
        message_content: errText,
        spoken_text: errText,
        detected_language: errLang,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewConversation = () => {
    stopSpeaking();
    if (isListening) {
      stopListening();
    }
    const nextConvId = generateConversationId();
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(getConversationStorageKey(user?.id), nextConvId);
    }
    hydratedConvRef.current = nextConvId;
    setConversationId(nextConvId);
    const activeLang = selectedLanguage === 'auto' ? language : selectedLanguage;
    setMessages([getInitialMessage(activeLang)]);
    setWorkflowStep('TALK');
    setActiveScheme(null);
    setInput('');
  };

  const handleMicToggle = () => {
    if (isListening) {
      stopListening();
    } else {
      stopSpeaking(); // stop any current playback before listening
      startListening(selectedLanguage);
    }
  };

  const handleToggleSpeak = (msg: ChatMessage) => {
    if (isSpeaking && speakingMessageId === msg.id) {
      stopSpeaking();
    } else {
      const textToSpeak = msg.spoken_text || msg.message_content;
      speak(textToSpeak, msg.detected_language || 'mr', msg.id);
    }
  };

  const renderStructuredData = (msg: ChatMessage) => {
    const widgetLang = ((msg.detected_language as 'en' | 'hi' | 'mr') ||
      (selectedLanguage === 'auto' ? language : selectedLanguage) ||
      'en') as 'en' | 'hi' | 'mr';

    // 1. Confirmation Request / Handoff Result Widget (Phase 6)
    if (
      msg.confirmation_data &&
      (msg.response_type === 'confirmation_request' || msg.response_type === 'confirmation_result')
    ) {
      const confPayload = msg.confirmation_data as ConfirmationPayload;
      const targetCode = confPayload.scheme_code || msg.active_scheme?.scheme_code || activeScheme?.scheme_code;
      return (
        <HandoffConfirmationWidget
          key={`confirm-${msg.id}`}
          data={confPayload}
          language={widgetLang}
          onConfirm={(confirmMeta) => {
            const confirmMsg =
              widgetLang === 'hi'
                ? 'हाँ, मैंने समीक्षित विवरण जांच लिए हैं और पुष्टि करता हूँ'
                : widgetLang === 'mr'
                ? 'होय, मी तपासलेले सर्व तपशील नक्की करतो'
                : 'Yes, I confirm the reviewed application details';
            handleSend(confirmMsg, {
              scheme_id: targetCode,
              workflow_step: 'CONFIRM',
              form_action: 'confirm_submit',
              expected_version: confirmMeta?.expected_version,
              expected_hash: confirmMeta?.expected_hash,
              idempotency_key: confirmMeta?.idempotency_key,
            });
          }}
          onRecordPortalReference={(officialReferenceNumber, meta) => {
            const refMsg =
              widgetLang === 'hi'
                ? `आधिकारिक पोर्टल संदर्भ संख्या दर्ज करें: ${officialReferenceNumber}`
                : widgetLang === 'mr'
                ? `अधिकृत पोर्टल संदर्भ क्रमांक नोंदवा: ${officialReferenceNumber}`
                : `Record official portal reference number: ${officialReferenceNumber}`;
            handleSend(refMsg, {
              scheme_id: targetCode,
              workflow_step: 'SUBMIT',
              form_action: 'record_portal_reference',
              official_reference_number: officialReferenceNumber,
              form_data: {
                application_id: meta?.application_id || confPayload.application_id,
                official_reference_number: officialReferenceNumber,
              },
            });
          }}
        />
      );
    }

    // 2. Interactive Universal Pre-Filled Form Widget (Phase 6)
    if (
      msg.form_draft_data &&
      (msg.response_type === 'form_draft' || msg.response_type === 'application_guide')
    ) {
      const draftPayload = msg.form_draft_data as FormDraftPayload;
      const targetCode = draftPayload.scheme_code || msg.active_scheme?.scheme_code || activeScheme?.scheme_code;
      return (
        <PreFilledFormWidget
          key={`form-${msg.id}-${draftPayload.scheme_code || 'scheme'}`}
          data={draftPayload}
          language={widgetLang}
          onSaveDraft={(formData) => {
            const saveMsg =
              widgetLang === 'hi'
                ? `${targetCode || ''} आवेदन ड्राफ्ट सहेजें`.trim()
                : widgetLang === 'mr'
                ? `${targetCode || ''} अर्जाचा मसुदा जतन करा`.trim()
                : `Save ${targetCode || ''} application draft`.trim();
            handleSend(saveMsg, {
              scheme_id: targetCode,
              workflow_step: 'PRE-FILL',
              form_action: 'save_draft',
              form_data: formData,
            });
          }}
          onConfirmSubmit={(formData) => {
            const procMsg =
              widgetLang === 'hi'
                ? `${targetCode || ''} आवेदन विवरण की पुष्टि करें`.trim()
                : widgetLang === 'mr'
                ? `${targetCode || ''} अर्जातील माहिती नक्की करा`.trim()
                : `Proceed to confirmation for ${targetCode || ''}`.trim();
            handleSend(procMsg, {
              scheme_id: targetCode,
              workflow_step: 'CONFIRM',
              form_action: 'request_confirmation',
              form_data: formData,
            });
          }}
        />
      );
    }

    // 3. Interactive Document Checklist Widget (Phase 3/5 Agentic Workflow)
    const checklistPayload =
      (msg.checklist_data?.items?.length ? (msg.checklist_data as ChecklistPayload) : null) ||
      (msg.response_type === 'document_checklist' && (msg.data as any)?.items?.length
        ? (msg.data as ChecklistPayload)
        : null);

    if (checklistPayload) {
      return (
        <InteractiveChecklistWidget
          key={`checklist-${msg.id}`}
          data={checklistPayload}
          schemeName={msg.active_scheme?.name || msg.active_scheme?.scheme_name || activeScheme?.name || activeScheme?.scheme_name}
          onPrefillClick={() =>
            handlePrefillClick(
              checklistPayload.scheme_code ||
                msg.active_scheme?.scheme_code ||
                activeScheme?.scheme_code
            )
          }
          onAskMissingDoc={(docTitle) =>
            handleAskMissingDoc(
              docTitle,
              checklistPayload.scheme_code || activeScheme?.scheme_code
            )
          }
        />
      );
    }

    if (msg.response_type === 'scheme_cards' && Array.isArray(msg.data)) {
      return (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3.5 w-full">
          {(msg.data as any[]).map((scheme) => (
            <Card key={scheme.id} hoverable className="border border-navy/10 shadow-subtle hover:shadow-premium bg-white flex flex-col justify-between">
              <CardContent className="p-4 space-y-2">
                <div className="flex items-center justify-between gap-1">
                  <Badge variant="category">{scheme.category}</Badge>
                  {scheme.eligibility_status && (
                    <Badge variant={scheme.eligibility_status}>
                      {scheme.eligibility_status === 'eligible'
                        ? (msg.detected_language === 'en' ? '● Eligible' : '● पात्र')
                        : scheme.eligibility_status === 'potentially_eligible'
                        ? (msg.detected_language === 'en' ? '● Potentially Eligible' : msg.detected_language === 'hi' ? '● संभावित पात्र' : '● संभाव्य पात्र')
                        : scheme.eligibility_status === 'insufficient_information'
                        ? (msg.detected_language === 'en' ? '● Info Needed' : msg.detected_language === 'hi' ? '● विवरण आवश्यक' : '● माहिती आवश्यक')
                        : scheme.eligibility_status === 'not_eligible'
                        ? (msg.detected_language === 'en' ? '● Ineligible' : '● अपात्र')
                        : scheme.eligibility_status.toUpperCase()}
                    </Badge>
                  )}
                </div>

                <h4 className="font-bold text-navy text-sm line-clamp-1 font-editorial">{scheme.name}</h4>
                <p className="text-[11px] text-navy/70 line-clamp-2 leading-relaxed">{scheme.benefits}</p>

                <div className="pt-2 flex items-center justify-between border-t border-navy/6">
                  <Link
                    to={`/schemes/${scheme.id}`}
                    className="text-xs font-bold text-saffron-dark hover:text-saffron flex items-center gap-1 group/link"
                  >
                    <span>{t.actions.viewDetails}</span>
                    <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover/link:translate-x-0.5" />
                  </Link>

                  {scheme.official_url && (
                    <a
                      href={scheme.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-navy/50 hover:text-navy"
                    >
                      Portal ↗
                    </a>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      );
    }

    if (msg.response_type === 'document_checklist' && Array.isArray(msg.data)) {
      return (
        <div className="space-y-2 mt-3.5 w-full">
          <div className="flex items-center gap-1.5 text-xs font-bold text-navy">
            <FileText className="w-4 h-4 text-saffron" />
            <span>
              {widgetLang === 'mr'
                ? 'आवश्यक कागदपत्रे पडताळणी यादी'
                : widgetLang === 'hi'
                ? 'आवश्यक दस्तावेज़ जांच सूची'
                : 'Required Document Checklist'}
            </span>
          </div>
          {(msg.data as DocumentRequirement[]).map((doc) => (
            <div key={doc.id} className="flex items-start justify-between gap-3 p-3 rounded-xl bg-white border border-navy/10 text-xs shadow-subtle">
              <div className="space-y-0.5">
                <span className="font-semibold text-navy capitalize">{doc.title || doc.document_type.replace(/_/g, ' ')}</span>
                {doc.guidance && <p className="text-[11px] text-navy/60">{doc.guidance}</p>}
                {doc.issuing_authority && (
                  <span className="inline-block text-[10px] text-navy/50 bg-ivory-100 px-2 py-0.5 rounded border border-navy/8">
                    {doc.issuing_authority}
                  </span>
                )}
              </div>
              <Badge variant={doc.is_mandatory ? 'saffron' : 'category'}>
                {doc.is_mandatory
                  ? widgetLang === 'mr' || widgetLang === 'hi'
                    ? 'अनिवार्य'
                    : 'Mandatory'
                  : widgetLang === 'mr'
                  ? 'पर्यायी'
                  : widgetLang === 'hi'
                  ? 'वैकल्पिक'
                  : 'Optional'}
              </Badge>
            </div>
          ))}
        </div>
      );
    }

    if (msg.response_type === 'application_guide' && msg.data) {
      const guide = msg.data as ApplicationGuideData;
      return (
        <div className="space-y-3 mt-3.5 w-full">
          <div className="bg-gradient-to-r from-saffron-50/70 to-ivory-50 p-3.5 rounded-2xl border border-saffron/25 shadow-subtle">
            <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
              <span className="text-xs font-bold font-editorial text-navy flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-saffron" />
                <span>{guide.scheme_name}</span>
                <span className="text-[10px] text-navy/60 font-mono bg-white px-2 py-0.5 rounded border border-navy/10">
                  {guide.scheme_code}
                </span>
              </span>
              {guide.citizen_eligibility_status && (
                <Badge variant={guide.citizen_eligibility_status as any}>
                  {guide.citizen_eligibility_status === 'eligible'
                    ? (msg.detected_language === 'en' ? '● Eligible Citizen' : '● पात्र नागरिक')
                    : guide.citizen_eligibility_status === 'not_eligible'
                    ? (msg.detected_language === 'en' ? '● Ineligible' : '● अपात्र')
                    : (msg.detected_language === 'en' ? '● Info Needed' : msg.detected_language === 'hi' ? '● विवरण आवश्यक' : '● माहिती आवश्यक')}
                </Badge>
              )}
            </div>

            {/* Step-by-step procedure list */}
            {guide.steps && guide.steps.length > 0 && (
              <div className="mt-3 space-y-2">
                <h5 className="text-[11px] font-bold text-navy uppercase tracking-wider flex items-center gap-1">
                  <span>
                    {msg.detected_language === 'en'
                      ? 'Official Application Procedure'
                      : msg.detected_language === 'hi'
                      ? 'आधिकारिक आवेदन प्रक्रिया'
                      : 'अधिकृत अर्ज प्रक्रिया'}
                  </span>
                </h5>
                <div className="space-y-1.5">
                  {guide.steps.map((step, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2.5 p-2 rounded-xl bg-white border border-navy/8 text-xs leading-relaxed shadow-xs"
                    >
                      <span className="w-5 h-5 rounded-full bg-saffron/15 text-saffron-dark font-bold text-[11px] flex items-center justify-center shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <span className="text-navy/90 text-[11.5px]">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions: Portal Button & Details link */}
            <div className="mt-3 pt-3 border-t border-navy/8 flex flex-wrap items-center justify-between gap-2">
              {guide.application_url && (
                <a
                  href={guide.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-saffron hover:bg-saffron-dark text-white font-bold text-xs rounded-xl shadow-subtle transition-all"
                >
                  <span>
                    {widgetLang === 'mr'
                      ? 'अधिकृत नोंदणी पोर्टल उघडा'
                      : widgetLang === 'hi'
                      ? 'आधिकारिक पंजीकरण पोर्टल खोलें'
                      : 'Open Official Registration Portal'}
                  </span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}

              {guide.scheme_id && (
                <Link
                  to={`/schemes/${guide.scheme_id}`}
                  className="text-xs font-semibold text-saffron-dark hover:text-saffron flex items-center gap-1"
                >
                  <span>
                    {widgetLang === 'mr'
                      ? 'योजना माहिती पहा'
                      : widgetLang === 'hi'
                      ? 'योजना विवरण देखें'
                      : 'View Scheme Details'}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              )}
            </div>

            {/* Offline Guidance Box */}
            {guide.offline_procedure && (
              <div className="mt-2 text-[11px] text-navy/70 bg-ivory-100/90 rounded-xl p-2.5 border border-navy/8 flex items-start gap-2">
                <Building2 className="w-3.5 h-3.5 text-navy/50 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-navy">
                    {widgetLang === 'mr'
                      ? 'ऑफलाइन अर्ज पर्याय (CSC / शासकीय केंद्र): '
                      : widgetLang === 'hi'
                      ? 'ऑफ़लाइन आवेदन विकल्प (CSC / सरकारी केंद्र): '
                      : 'Offline Application Option (CSC / Govt Center): '}
                  </span>
                  <span>{guide.offline_procedure}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      );
    }

    if (msg.response_type === 'benefits_info' && msg.data) {
      const bInfo = msg.data as BenefitsInfoData;
      return (
        <div className="mt-3 p-3.5 rounded-2xl bg-emerald-50/70 border border-emerald-200/60 shadow-subtle space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-emerald-950 flex items-center gap-1.5">
              <Coins className="w-4 h-4 text-emerald-600" />
              <span>{bInfo.scheme_name} ({bInfo.scheme_code})</span>
            </span>
            <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full">
              {widgetLang === 'mr'
                ? 'थेट लाभ हस्तांतरण (DBT)'
                : widgetLang === 'hi'
                ? 'प्रत्यक्ष लाभ अंतरण (DBT)'
                : 'Scheme Benefits'}
            </span>
          </div>
          <p className="text-xs font-medium text-emerald-900 leading-relaxed bg-white/80 p-2.5 rounded-xl border border-emerald-100">
            {bInfo.benefits}
          </p>
          {bInfo.official_url && (
            <div className="pt-1 flex justify-end">
              <a
                href={bInfo.official_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] text-emerald-700 hover:text-emerald-900 font-semibold flex items-center gap-1"
              >
                <span>
                  {widgetLang === 'mr'
                    ? 'अधिकृत संकेतस्थळ'
                    : widgetLang === 'hi'
                    ? 'आधिकारिक वेबसाइट'
                    : 'Official Website'}
                </span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          )}
        </div>
      );
    }

    if (msg.response_type === 'status_tracking' && msg.data) {
      const sTrack = msg.data as StatusTrackingData;
      return (
        <div className="mt-3 p-3.5 rounded-2xl bg-blue-50/70 border border-blue-200/60 shadow-subtle space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-blue-950 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-blue-600" />
              <span>
                {widgetLang === 'mr'
                  ? 'नोंदणीनंतरची प्रक्रिया व स्थिती'
                  : widgetLang === 'hi'
                  ? 'स्थिति और अगले कदम'
                  : 'Status & Next Steps'}
              </span>
            </span>
            <span className="text-[10px] bg-blue-100 text-blue-800 font-bold px-2 py-0.5 rounded-full">
              {sTrack.scheme_code}
            </span>
          </div>
          {sTrack.post_steps && sTrack.post_steps.length > 0 && (
            <div className="space-y-1.5">
              {sTrack.post_steps.map((step, idx) => (
                <div key={idx} className="flex items-start gap-2 bg-white/80 p-2 rounded-xl border border-blue-100 text-xs text-blue-950">
                  <span className="w-4 h-4 rounded-full bg-blue-200 text-blue-800 text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {idx + 1}
                  </span>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          )}
          {sTrack.status_url && (
            <div className="pt-1">
              <a
                href={sTrack.status_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-subtle transition-all"
              >
                <span>
                  {widgetLang === 'mr'
                    ? 'अर्जाची स्थिती तपासा'
                    : widgetLang === 'hi'
                    ? 'आवेदन स्थिति जांचें'
                    : 'Official Scheme Portal'}
                </span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          )}
        </div>
      );
    }

    return null;
  };

  const handlePrefillClick = (schemeCode?: string) => {
    const targetCode =
      schemeCode ||
      activeScheme?.scheme_code ||
      (typeof activeScheme === 'string' ? activeScheme : undefined);
    const activeLang = selectedLanguage === 'auto' ? language : selectedLanguage;
    const msgText =
      activeLang === 'en'
        ? targetCode
          ? `Pre-fill application draft for ${targetCode}`
          : 'Pre-fill my application draft'
        : activeLang === 'hi'
        ? targetCode
          ? `मेरे लिए ${targetCode} योजना का आवेदन मसौदा भरें`
          : 'मेरे लिए आवेदन मसौदा भरें'
        : targetCode
        ? `माझ्यासाठी ${targetCode} योजनेचा अर्ज मसुदा तयार करा`
        : 'माझ्यासाठी अर्जाचा मसुदा तयार करा';
    handleSend(
      msgText,
      {
        scheme_id: targetCode,
        workflow_step: 'PRE-FILL',
        form_action: 'prefill_form',
      }
    );
  };

  const handleAskMissingDoc = (docTitle: string, schemeCode?: string) => {
    const targetCode =
      schemeCode ||
      activeScheme?.scheme_code ||
      (typeof activeScheme === 'string' ? activeScheme : undefined);
    const msgText =
      language === 'en'
        ? `I do not have '${docTitle}', what should I do?`
        : language === 'hi'
        ? `मेरे पास '${docTitle}' नहीं है, मैं क्या करूँ?`
        : `माझ्याकडे '${docTitle}' उपलब्ध नाही, मी काय करावे?`;
    handleSend(msgText, {
      scheme_id: targetCode,
      workflow_step: 'CHECKLIST',
    });
  };

  const handleStepClick = (stage: WorkflowStage) => {
    if (stage === 'MATCH') {
      const msgText =
        language === 'en'
          ? 'Show my eligible schemes'
          : language === 'hi'
          ? 'मुझे पात्र योजनाएं दिखाएं'
          : 'मला पात्र योजना दाखवा';
      handleSend(msgText, { workflow_step: 'MATCH' });
    } else if (stage === 'CHECKLIST') {
      const msgText =
        language === 'en'
          ? 'Which documents do I need?'
          : language === 'hi'
          ? 'मुझे कौन से दस्तावेज़ चाहिए?'
          : 'मला कोणती कागदपत्रे लागतील?';
      handleSend(msgText, { workflow_step: 'CHECKLIST' });
    } else if (stage === 'PRE-FILL') {
      const msgText =
        language === 'en'
          ? 'Pre-fill my application draft'
          : language === 'hi'
          ? 'मेरे लिए आवेदन का मसौदा तैयार करें'
          : 'माझ्यासाठी अर्जाचा मसुदा भरा';
      handleSend(msgText, { workflow_step: 'PRE-FILL' });
    } else if (stage === 'CONFIRM') {
      const msgText =
        language === 'en'
          ? 'Confirm my application readiness packet'
          : language === 'hi'
          ? 'आवेदन तत्परता पैकेट की पुष्टि करें'
          : 'अंतिम अर्ज सज्जता संच नक्की करा';
      handleSend(msgText, { workflow_step: 'CONFIRM' });
    } else {
      const msgText =
        language === 'en'
          ? 'Hello, I want information about welfare schemes'
          : language === 'hi'
          ? 'नमस्ते, मुझे सरकारी योजनाओं की जानकारी चाहिए'
          : 'नमस्कार, मला योजनांबद्दल माहिती हवी आहे';
      handleSend(msgText, { workflow_step: 'TALK' });
    }
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col h-[calc(100vh-190px)] min-h-[560px] bg-white rounded-3xl border border-navy/8 shadow-subtle overflow-hidden relative">
      {/* Chat Header */}
      <div className="px-5 py-3.5 border-b border-navy/8 bg-ivory-50/80 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-navy text-white flex items-center justify-center shadow-subtle relative">
            <Bot className="w-5 h-5 text-saffron" />
            {isSpeaking && (
              <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-saffron rounded-full animate-ping" />
            )}
          </div>
          <div>
            <h2 className="text-sm font-bold font-editorial text-navy flex items-center gap-2">
              <span>योजना साथी (Scheme Saathi Voice AI)</span>
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-sage-green bg-sage-light px-2 py-0.5 rounded-full border border-sage/30">
                <span className="w-1.5 h-1.5 rounded-full bg-sage-green animate-pulse" />
                Live Voice Assistant
              </span>
            </h2>
            <p className="text-[11px] text-navy/50">
              मराठी • हिंदी • English | Grounded in PostgreSQL & Eligibility Rules
            </p>
          </div>
        </div>

        {/* Language Selector, New Chat & Global Audio Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleNewConversation}
            disabled={loading}
            className="flex items-center gap-1 bg-white border border-navy/12 hover:border-saffron/40 hover:bg-ivory-50 text-navy font-semibold text-xs px-2.5 py-1 rounded-xl shadow-subtle transition-colors disabled:opacity-50"
            title="Start a new conversation"
          >
            <RotateCcw className="w-3.5 h-3.5 text-navy/60" />
            <span>
              {(selectedLanguage === 'auto' ? language : selectedLanguage) === 'mr'
                ? 'नवीन चर्चा'
                : (selectedLanguage === 'auto' ? language : selectedLanguage) === 'hi'
                ? 'नई बातचीत'
                : 'New Chat'}
            </span>
          </button>

          {/* Language Selector Dropdown */}
          <div className="flex items-center gap-1 bg-white border border-navy/12 rounded-xl px-2.5 py-1 text-xs shadow-subtle">
            <Languages className="w-3.5 h-3.5 text-navy/50" />
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value as AssistantLanguage)}
              className="bg-transparent text-navy font-semibold text-xs focus:outline-none cursor-pointer pr-1"
            >
              <option value="auto">🌐 Auto Detect</option>
              <option value="mr">🚩 मराठी (Marathi)</option>
              <option value="hi">🇮🇳 हिंदी (Hindi)</option>
              <option value="en">🇬🇧 English</option>
            </select>
          </div>

          {/* Audio playback global controls if active */}
          {isSpeaking && (
            <div className="flex items-center gap-1">
              <button
                onClick={isPaused ? resumeSpeaking : pauseSpeaking}
                className="flex items-center gap-1 text-xs bg-saffron-light text-saffron-dark border border-saffron/30 px-2.5 py-1 rounded-xl font-semibold shadow-subtle hover:bg-saffron/20 transition-colors"
                title={isPaused ? "Resume Audio" : "Pause Audio"}
              >
                {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                <span>{isPaused ? 'Resume' : 'Pause'}</span>
              </button>
              <button
                onClick={stopSpeaking}
                className="flex items-center gap-1 text-xs bg-rose-50 text-rose-700 border border-rose-200 px-2.5 py-1 rounded-xl font-semibold shadow-subtle hover:bg-rose-100 transition-colors"
                title="Stop Audio"
              >
                <VolumeX className="w-3.5 h-3.5" />
                <span>Stop</span>
              </button>
            </div>
          )}

          <div className="hidden sm:flex items-center gap-1 text-xs text-navy/60 font-medium pl-1">
            <ShieldCheck className="w-4 h-4 text-sage-green" />
            <span>Private</span>
          </div>
        </div>
      </div>

      {/* 5-Stage Agentic Workflow Stepper (TALK -> MATCH -> CHECKLIST -> PRE-FILL -> CONFIRM) */}
      <WorkflowStepper
        currentStep={workflowStep}
        activeScheme={activeScheme}
        onStepClick={handleStepClick}
      />

      {/* Microphone Permission / STT Error Alert Banner */}
      {sttError && (
        <div className="px-5 py-2.5 bg-rose-50 border-b border-rose-200 flex items-center justify-between text-xs text-rose-900 animate-fade-in-up">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{sttError}</span>
          </div>
          <button
            onClick={() => handleMicToggle()}
            className="text-[11px] font-bold text-rose-700 underline underline-offset-2 ml-2 shrink-0"
          >
            Retry Mic
          </button>
        </div>
      )}

      {/* Active Voice Notice Banner (e.g. Marathi TTS fallback to Hindi Lekha) */}
      {activeVoiceNotice && (
        <div className="px-5 py-2 bg-amber-50/90 border-b border-amber-200 text-xs text-amber-900 flex items-center gap-2 animate-fade-in-up">
          <Volume2 className="w-4 h-4 text-amber-700 shrink-0" />
          <span>{activeVoiceNotice}</span>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-ivory-50/30">
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const isThisSpeaking = isSpeaking && speakingMessageId === msg.id;

          return (
            <div key={msg.id} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
              {!isUser && (
                <div className="w-8 h-8 rounded-full bg-saffron-light text-saffron-dark flex items-center justify-center shrink-0 mt-0.5 border border-saffron/30 shadow-subtle">
                  <Sparkles className="w-4 h-4 text-saffron-vibrant" />
                </div>
              )}

              <div
                className={`max-w-[88%] sm:max-w-[78%] rounded-2xl p-4 text-sm leading-relaxed transition-all duration-200 ${
                  isUser
                    ? 'bg-navy text-white rounded-tr-xs shadow-subtle'
                    : 'bg-white text-navy rounded-tl-xs border border-navy/8 shadow-subtle'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="whitespace-pre-wrap leading-relaxed flex-1">{msg.message_content}</p>

                  {/* Audio Speaker Listen Button on Assistant Messages */}
                  {!isUser && (
                    <div className="flex items-center gap-1 shrink-0">
                      {isThisSpeaking && (
                        <button
                          onClick={isPaused ? resumeSpeaking : pauseSpeaking}
                          title={isPaused ? "Resume Audio" : "Pause Audio"}
                          className="p-1.5 rounded-lg border bg-saffron-light text-saffron-dark border-saffron/40 hover:bg-saffron/20 transition-all"
                        >
                          {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                        </button>
                      )}
                      <button
                        onClick={() => handleToggleSpeak(msg)}
                        title={isThisSpeaking ? 'Stop speaking' : 'Listen to this response'}
                        className={`p-1.5 rounded-lg border transition-all ${
                          isThisSpeaking
                            ? 'bg-saffron text-white border-saffron animate-pulse shadow-subtle'
                            : 'bg-ivory-100 text-navy/60 hover:text-navy hover:bg-ivory-200 border-navy/10'
                        }`}
                      >
                        {isThisSpeaking ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  )}
                </div>

                {/* Subtle notification for Marathi TTS fallback */}
                {!isUser && msg.detected_language === 'mr' && (
                  <div className="mt-2 text-[10.5px] text-amber-900 bg-amber-50/80 border border-amber-200/60 rounded-lg px-2.5 py-1 flex items-center gap-1.5">
                    <Volume2 className="w-3 h-3 text-amber-700 shrink-0" />
                    <span>मराठी उच्चार: हिंदी आवाज (Lekha) द्वारे उपलब्ध (ब्राउझरमध्ये मूळ मराठी व्हॉइस उपलब्ध नाही)</span>
                  </div>
                )}

                {renderStructuredData(msg)}

                {/* Suggested follow-up chips if present */}
                {msg.suggested_followups && msg.suggested_followups.length > 0 && (
                  <div className="pt-3 mt-3 border-t border-navy/8 flex flex-wrap gap-1.5">
                    {msg.suggested_followups.map((chip, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSend(chip)}
                        className="text-[11px] px-2.5 py-1 rounded-full bg-ivory-100 hover:bg-saffron-light text-navy/80 hover:text-saffron-dark border border-navy/10 transition-colors text-left"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between mt-2 pt-1 text-[10px] text-navy/40 border-t border-navy/5">
                  <span className="flex items-center gap-1.5">
                    <span>{msg.detected_language ? `Lang: ${msg.detected_language.toUpperCase()}` : ''}</span>
                    <span>•</span>
                    <span className="font-medium text-navy/60">
                      {msg.engine_mode === 'gemini_grounded' ? 'Gemini 1.5 Pro (Grounded)' : 'Deterministic Rules Mode'}
                    </span>
                  </span>
                  <span>{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </div>

              {isUser && (
                <div className="w-8 h-8 rounded-full bg-navy/10 text-navy flex items-center justify-center shrink-0 mt-0.5 font-bold text-xs">
                  <User className="w-4 h-4 text-navy" />
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3 items-center text-navy/60 text-xs italic">
            <div className="w-8 h-8 rounded-full bg-saffron-light text-saffron-dark flex items-center justify-center animate-spin">
              <Sparkles className="w-4 h-4 text-saffron-vibrant" />
            </div>
            <span>साथी विचार करत आहे... (Evaluating official rules and database guidelines...)</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Live Voice Recording Waveform Overlay */}
      {isListening && (
        <div className="px-5 py-3 bg-linear-to-r from-saffron-50 via-white to-sage-light/30 border-t border-saffron/30 flex items-center justify-between gap-4 animate-fade-in-up">
          <div className="flex items-center gap-3">
            {/* Pulsing red mic dot */}
            <div className="relative flex items-center justify-center">
              <span className="w-3 h-3 bg-rose-600 rounded-full animate-ping absolute" />
              <span className="w-3 h-3 bg-rose-600 rounded-full relative" />
            </div>

            <div className="space-y-0.5">
              <span className="text-xs font-bold text-navy flex items-center gap-1.5">
                <span>Listening ({selectedLanguage === 'mr' ? 'मराठी' : selectedLanguage === 'hi' ? 'हिंदी' : 'English'})...</span>
                {/* Audio wave simulation bars */}
                <span className="flex items-center gap-0.5 ml-1">
                  <span className="w-1 h-3 bg-saffron-vibrant rounded-full animate-pulse" />
                  <span className="w-1 h-5 bg-saffron rounded-full animate-pulse delay-75" />
                  <span className="w-1 h-2 bg-saffron-vibrant rounded-full animate-pulse delay-150" />
                  <span className="w-1 h-4 bg-saffron rounded-full animate-pulse delay-100" />
                </span>
              </span>
              <p className="text-[11px] text-navy/60 italic">
                {interimTranscript || 'Speak now in your natural language... (बोलणे सुरू करा)'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={stopListening} leftIcon={<StopCircle className="w-3.5 h-3.5" />}>
              Done / Send
            </Button>
          </div>
        </div>
      )}

      {/* Suggested Quick Prompt Chips */}
      <div className="px-5 py-2 border-t border-navy/8 bg-ivory/60 flex items-center gap-2 overflow-x-auto scrollbar-none">
        {[
          { label: 'मी शेतकरी आहे. मला कोणत्या योजना मिळतील?', lang: 'mr' },
          { label: 'मला PM किसान योजनेसाठी पात्रता आहे का?', lang: 'mr' },
          { label: 'मला कोणती कागदपत्रे लागतील?', lang: 'mr' },
          { label: 'मैं महाराष्ट्र का रहने वाला हूँ, मुझे कौन सी योजनाएँ मिलेंगी?', lang: 'hi' },
          { label: 'Mujhe farming ke liye government scheme chahiye.', lang: 'mixed' },
        ].map((item, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(item.label)}
            className="text-xs px-3.5 py-1.5 rounded-full bg-white text-navy/80 border border-navy/12 hover:border-saffron hover:text-saffron-dark transition-all duration-200 whitespace-nowrap shrink-0 shadow-subtle"
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Input Form Bar with Microphone Button */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
        className="p-3 sm:p-4 border-t border-navy/8 bg-white flex items-center gap-2 sm:gap-3"
      >
        {/* Microphone Button */}
        <button
          type="button"
          onClick={handleMicToggle}
          title={isListening ? 'Stop listening' : 'Start voice input (मराठी, हिंदी, English)'}
          className={`p-3 rounded-2xl border transition-all duration-200 shrink-0 flex items-center justify-center ${
            isListening
              ? 'bg-rose-600 text-white border-rose-700 shadow-premium scale-105 animate-pulse'
              : 'bg-saffron-light text-saffron-dark hover:bg-saffron hover:text-white border-saffron/30 shadow-subtle'
          }`}
        >
          {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>

        {/* Text / Speech Transcript Input Field */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            selectedLanguage === 'mr'
              ? 'माईक दाबा किंवा येथे प्रश्न टाईप करा (उदा. मी शेतकरी आहे, मला कोणती योजना मिळेल?)...'
              : selectedLanguage === 'hi'
              ? 'माइक दबाएं या टाइप करें (उदा. मैं किसान हूँ, मुझे किस योजना का लाभ मिलेगा?)...'
              : 'Ask Scheme Saathi anything by voice or typing...'
          }
          className="flex-1 bg-ivory-50 border border-navy/15 rounded-xl px-4 py-2.5 text-sm text-navy placeholder-navy/40 focus:outline-none focus:ring-2 focus:ring-navy/15 focus:border-navy transition-all"
        />

        {/* Send Button */}
        <Button type="submit" variant="saffron" size="md" disabled={!input.trim() || loading} className="shrink-0 px-5">
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </div>
  );
};
