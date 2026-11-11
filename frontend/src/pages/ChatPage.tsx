import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { agentService } from '@/services/api/agentService';
import {
  ChatMessage,
  DocumentRequirement,
  ApplicationGuideData,
  BenefitsInfoData,
  StatusTrackingData,
} from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { useVoiceAssistant, AssistantLanguage } from '@/hooks/useVoiceAssistant';
import { Button } from '@/components/common/Button';
import { Card, CardContent } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
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
} from 'lucide-react';

export const ChatPage: React.FC = () => {
  const { t } = useLanguage();

  const [conversationId] = useState<string>(
    () => `conv-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  );
  const [selectedLanguage, setSelectedLanguage] = useState<AssistantLanguage>('auto');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-01',
      conversation_id: 'conv-init',
      role: 'assistant',
      message_content:
        'नमस्ते! मी तुमचा योजना साथी आहे. आपण मराठी, हिंदी किंवा इंग्रजीत बोलून किंवा टाईप करून शासकीय योजनांबद्दल विचारू शकता. मी आपल्या प्रोफाईलनुसार अचूक पात्रता आणि कागदपत्रे सांगेन.\n\nनमस्ते! मैं आपका योजना साथी हूँ। आप मुझसे बोलकर या लिखकर सरकारी योजनाओं की जानकारी, पात्रता और जरूरी दस्तावेज पूछ सकते हैं।',
      spoken_text:
        'नमस्ते! मी तुमचा योजना साथी आहे. आपण मराठी, हिंदी किंवा इंग्रजीत बोलून किंवा टाईप करून शासकीय योजनांबद्दल विचारू शकता. मी आपल्या प्रोफाईलनुसार अचूक पात्रता आणि कागदपत्रे सांगेन. नमस्ते! मैं आपका योजना साथी हूँ। आप मुझसे बोलकर या लिखकर सरकारी योजनाओं की जानकारी, पात्रता और जरूरी दस्तावेज पूछ सकते हैं।',
      detected_language: 'mr',
      response_type: 'text',
      suggested_followups: [
        'मी शेतकरी आहे. मला कोणत्या योजना मिळू शकतात?',
        'मला PM किसान योजनेसाठी पात्रता आहे का?',
        'मला कोणती कागदपत्रे लागतील?',
        'महाराष्ट्र शासनाच्या योजना सांगा',
      ],
      created_at: new Date().toISOString(),
    },
  ]);

  const [input, setInput] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  const handleSend = async (messageText: string) => {
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
      const response = await agentService.sendMessage(query, conversationId, selectedLanguage);

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
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // Automatically speak complete conversational response if speech recognition was used
      if (isSttSupported) {
        const textToSpeak = assistantMsg.spoken_text || assistantMsg.message_content;
        speak(textToSpeak, assistantMsg.detected_language || 'mr', assistantMsg.id);
      }
    } catch (err) {
      console.error('Chat error:', err);
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        conversation_id: 'conv-active',
        role: 'assistant',
        message_content:
          selectedLanguage === 'mr'
            ? 'माफ करा, सर्व्हरशी संपर्क साधताना समस्या आली. कृपया पुन्हा प्रयत्न करा.'
            : 'क्षमा करें, अनुरोध संसाधित करने में समस्या हुई। कृपया पुनः प्रयास करें।',
        spoken_text:
          selectedLanguage === 'mr'
            ? 'माफ करा, सर्व्हरशी संपर्क साधताना समस्या आली. कृपया पुन्हा प्रयत्न करा.'
            : 'क्षमा करें, अनुरोध संसाधित करने में समस्या हुई। कृपया पुनः प्रयास करें।',
        detected_language: selectedLanguage === 'auto' ? 'mr' : selectedLanguage,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
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
                        ? '● पात्र'
                        : scheme.eligibility_status === 'potentially_eligible'
                        ? '● संभाव्य पात्र'
                        : scheme.eligibility_status === 'insufficient_information'
                        ? '● माहिती आवश्यक'
                        : scheme.eligibility_status === 'not_eligible'
                        ? '● अपात्र'
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
            <span>आवश्यक कागदपत्रे पडताळणी यादी (Required Document Checklist)</span>
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
                {doc.is_mandatory ? 'Mandatory' : 'Optional'}
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
                    ? '● पात्र नागरिक'
                    : guide.citizen_eligibility_status === 'not_eligible'
                    ? '● अपात्र'
                    : '● माहिती आवश्यक'}
                </Badge>
              )}
            </div>

            {/* Step-by-step procedure list */}
            {guide.steps && guide.steps.length > 0 && (
              <div className="mt-3 space-y-2">
                <h5 className="text-[11px] font-bold text-navy uppercase tracking-wider flex items-center gap-1">
                  <span>अधिकृत अर्ज प्रक्रिया (Step-by-Step Procedure)</span>
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
                  <span>अधिकृत नोंदणी पोर्टल उघडा</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}

              {guide.scheme_id && (
                <Link
                  to={`/schemes/${guide.scheme_id}`}
                  className="text-xs font-semibold text-saffron-dark hover:text-saffron flex items-center gap-1"
                >
                  <span>योजना माहिती पहा</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              )}
            </div>

            {/* Offline Guidance Box */}
            {guide.offline_procedure && (
              <div className="mt-2 text-[11px] text-navy/70 bg-ivory-100/90 rounded-xl p-2.5 border border-navy/8 flex items-start gap-2">
                <Building2 className="w-3.5 h-3.5 text-navy/50 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-navy">ऑफलाइन अर्ज पर्याय (CSC / शासकीय केंद्र): </span>
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
              DBT थेट बँक जमा
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
                <span>अधिकृत संकेतस्थळ (Official Website)</span>
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
              <span>नोंदणीनंतरची प्रक्रिया व स्थिती (Status & Next Steps)</span>
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
                <span>अर्जाची स्थिती तपासा (Check Status Portal)</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          )}
        </div>
      );
    }

    return null;
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

        {/* Language Selector & Global Audio Controls */}
        <div className="flex items-center gap-2">
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
