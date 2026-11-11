import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { PendingAction } from '../types';
import { SpeechPlayerButton } from '../components/SpeechPlayerButton';
import { VoiceVisualizerModal } from '../components/VoiceVisualizerModal';
import { SpeechRecognizer, isSpeechRecognitionSupported } from '../utils/speechRecognition';
import { speechSynthesizer } from '../utils/speechSynthesis';
import {
  Sparkles,
  Send,
  Mic,
  MicOff,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  HelpCircle,
  User,
  Bot,
  Loader2,
  Volume2,
} from 'lucide-react';

interface LocalMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  pendingAction?: PendingAction | null;
  timestamp: string;
}

export const ChatView: React.FC = () => {
  const { t, language } = useLanguage();
  const { user } = useAuth();

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [autoRead, setAutoRead] = useState<boolean>(false);
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState<boolean>(false);
  const [interimTranscript, setInterimTranscript] = useState<string>('');
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognizerRef = useRef<SpeechRecognizer | null>(null);

  // Initial welcome message
  useEffect(() => {
    const welcomeText =
      language === 'hi'
        ? `नमस्ते ${user?.profile?.full_name || 'नागरिक'} जी! मैं आपका योजना साथी हूँ। आप मुझसे किसी भी सरकारी योजना की पात्रता, आवश्यक दस्तावेज़ या आवेदन की स्थिति के बारे में पूछ सकते हैं।`
        : `Hello ${user?.profile?.full_name || 'Citizen'}! I am Scheme Saathi. You can ask me about scheme eligibility, required documents, or application status in English or Hindi.`;

    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: welcomeText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  }, [language, user]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSending]);

  // Web Speech API Voice Input
  const handleVoiceInput = () => {
    if (!isSpeechRecognitionSupported()) {
      setVoiceError(
        language === 'hi'
          ? 'आपके ब्राउज़र में आवाज़ पहचान (Voice Recognition) समर्थित नहीं है। कृपया टाइप करके प्रश्न पूछें।'
          : 'Speech recognition is not supported in your browser. Please type your message.'
      );
      setTimeout(() => setVoiceError(null), 5000);
      return;
    }

    if (isListening) {
      recognizerRef.current?.stop();
      setIsListening(false);
      setIsVoiceModalOpen(false);
      return;
    }

    setInterimTranscript('');
    setIsVoiceModalOpen(true);

    const recognizer = new SpeechRecognizer(
      {
        onStart: () => setIsListening(true),
        onInterimResult: (transcript) => {
          setInterimTranscript(transcript);
        },
        onFinalResult: (transcript) => {
          setInterimTranscript(transcript);
          setInputText((prev) => (prev ? `${prev} ${transcript}` : transcript));
        },
        onError: (err) => {
          console.warn('Speech recognition error:', err);
          setIsListening(false);
        },
        onEnd: () => {
          setIsListening(false);
        },
      },
      { lang: language === 'hi' ? 'hi-IN' : 'en-IN' }
    );

    recognizerRef.current = recognizer;
    recognizer.start();
  };

  const handleCloseVoiceModal = () => {
    recognizerRef.current?.stop();
    setIsVoiceModalOpen(false);
    setIsListening(false);
  };

  const handleConfirmVoiceModal = () => {
    recognizerRef.current?.stop();
    setIsVoiceModalOpen(false);
    setIsListening(false);
    if (interimTranscript.trim()) {
      handleSendMessage(interimTranscript.trim());
      setInterimTranscript('');
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || isSending) return;

    setInputText('');

    const userMsg: LocalMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsSending(true);

    try {
      const data = await api.agent.chat(text, conversationId);
      if (data.conversation_id && !conversationId) {
        setConversationId(data.conversation_id);
      }

      const botMsg: LocalMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: data.message,
        pendingAction: data.pending_action,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, botMsg]);

      // If autoRead is enabled, speak the assistant's reply automatically
      if (autoRead && data.message) {
        speechSynthesizer.speak(data.message, {
          lang: language === 'hi' ? 'hi-IN' : 'en-IN',
        });
      }
    } catch (err: any) {
      console.error('Chat error:', err);
      const errMsg: LocalMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content:
          language === 'hi'
            ? 'क्षमा करें, संदेश संसाधित करने में समस्या हुई। कृपया पुनः प्रयास करें।'
            : 'Sorry, there was a problem processing your request. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const handleConfirmAction = async (actionId: string, msgIndex: number) => {
    try {
      await api.agent.confirmAction(actionId);
      setMessages((prev) =>
        prev.map((m, idx) =>
          idx === msgIndex && m.pendingAction
            ? { ...m, pendingAction: { ...m.pendingAction, status: 'CONFIRMED' } }
            : m
        )
      );
      // Append confirmation acknowledgement
      const ackMsg: LocalMessage = {
        id: `ack-${Date.now()}`,
        role: 'assistant',
        content:
          language === 'hi'
            ? 'कार्रवाई सफलतापूर्वक निष्पादित और डेटाबेस में सहेजी गई।'
            : 'Action successfully confirmed and saved to your profile.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, ackMsg]);
    } catch (err: any) {
      console.error('Confirmation error:', err);
      alert(err.response?.data?.error?.message || 'पुष्टि विफल रही / Confirmation failed');
    }
  };

  const handleCancelAction = async (actionId: string, msgIndex: number) => {
    try {
      await api.agent.cancelAction(actionId);
      setMessages((prev) =>
        prev.map((m, idx) =>
          idx === msgIndex && m.pendingAction
            ? { ...m, pendingAction: { ...m.pendingAction, status: 'CANCELLED' } }
            : m
        )
      );
    } catch (err: any) {
      console.error('Cancellation error:', err);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-4xl mx-auto bg-white border-x border-slate-200">
      {/* Subheader Controls */}
      <div className="px-4 py-2 border-b border-slate-200 bg-slate-50/70 flex items-center justify-between text-xs">
        <div className="flex items-center space-x-1.5 text-slate-700">
          <Sparkles className="w-3.5 h-3.5 text-orange-600" />
          <span className="font-semibold">
            {language === 'hi' ? 'योजना साथी AI सहायक' : 'Scheme Saathi AI Assistant'}
          </span>
        </div>

        <button
          type="button"
          onClick={() => setAutoRead(!autoRead)}
          className={`flex items-center space-x-1 px-2.5 py-1 rounded-xl text-xs font-semibold transition-all ${
            autoRead
              ? 'bg-orange-100 text-orange-700 border border-orange-300 shadow-sm'
              : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/60'
          }`}
          title={language === 'hi' ? 'उत्तर स्वतः सुनें' : 'Auto-read assistant responses'}
          aria-label={
            autoRead
              ? language === 'hi'
                ? 'ऑटो-रीड चालू'
                : 'Auto-Read On'
              : language === 'hi'
              ? 'ऑटो-रीड'
              : 'Auto-Read'
          }
        >
          <Volume2 className="w-3.5 h-3.5" />
          <span>
            {language === 'hi'
              ? autoRead
                ? 'ऑटो-रीड चालू'
                : 'ऑटो-रीड'
              : autoRead
              ? 'Auto-Read On'
              : 'Auto-Read'}
          </span>
        </button>
      </div>

      {/* Voice Error Notification Toast */}
      {voiceError && (
        <div className="px-4 py-2.5 bg-rose-50 border-b border-rose-200 text-rose-800 text-xs flex items-center justify-between animate-fade-in">
          <span>{voiceError}</span>
          <button
            type="button"
            onClick={() => setVoiceError(null)}
            className="text-rose-500 hover:text-rose-700 font-bold ml-2"
          >
            &times;
          </button>
        </div>
      )}

      {/* Chat Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.map((msg, index) => (
          <div
            key={msg.id}
            className={`flex items-start space-x-3 ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold shadow-sm ${
                msg.role === 'user'
                  ? 'bg-orange-600 text-white'
                  : 'bg-gradient-to-tr from-amber-500 to-green-600 text-white'
              }`}
            >
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Bubble */}
            <div className={`max-w-[85%] sm:max-w-[75%] space-y-2`}>
              <div
                className={`p-3.5 sm:p-4 rounded-2xl text-sm leading-relaxed shadow-sm whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-orange-600 text-white rounded-tr-none'
                    : 'bg-slate-100/90 text-slate-800 rounded-tl-none border border-slate-200/60'
                }`}
              >
                {msg.content}
                <div
                  className={`text-[10px] mt-1.5 flex items-center ${
                    msg.role === 'user' ? 'text-orange-200 justify-end' : 'text-slate-400 justify-between'
                  }`}
                >
                  {msg.role === 'assistant' && (
                    <SpeechPlayerButton text={msg.content} />
                  )}
                  <span>{msg.timestamp}</span>
                </div>
              </div>

              {/* Pending Action Card (Explicit Citizen Agency) */}
              {msg.pendingAction && (
                <div className="p-4 bg-amber-50/90 border border-amber-300 rounded-2xl shadow-sm text-xs space-y-3 animate-fade-in">
                  <div className="flex items-center justify-between border-b border-amber-200 pb-2">
                    <div className="flex items-center space-x-1.5 font-bold text-amber-900">
                      <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                      <span>{t('chat.action_pending')}</span>
                    </div>
                    <span className="text-[10px] text-amber-700 flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>15 मिनट के लिए वैध / Valid for 15m</span>
                    </span>
                  </div>

                  <div>
                    <h4 className="font-semibold text-slate-800 mb-1">
                      {language === 'hi' ? msg.pendingAction.summary.hi : msg.pendingAction.summary.en}
                    </h4>
                    <div className="bg-white/80 p-2.5 rounded-lg border border-amber-200 space-y-1 text-slate-700 font-mono text-[11px]">
                      {Object.entries(msg.pendingAction.payload).map(([k, v]) => (
                        <div key={k} className="flex justify-between">
                          <span className="text-slate-500 font-sans">{k}:</span>
                          <span className="font-semibold text-slate-900 truncate max-w-[180px]">
                            {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {msg.pendingAction.status === 'PENDING' ? (
                    <div className="flex items-center space-x-2 pt-1">
                      <button
                        onClick={() => handleConfirmAction(msg.pendingAction!.id, index)}
                        className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-semibold flex items-center justify-center space-x-1.5 shadow-sm transition-colors"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{t('chat.action_confirm')}</span>
                      </button>
                      <button
                        onClick={() => handleCancelAction(msg.pendingAction!.id, index)}
                        className="py-2 px-3 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-xl font-medium flex items-center justify-center space-x-1 transition-colors"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>{t('chat.action_cancel')}</span>
                      </button>
                    </div>
                  ) : msg.pendingAction.status === 'CONFIRMED' ? (
                    <div className="p-2 bg-emerald-100 text-emerald-800 rounded-lg text-center font-semibold flex items-center justify-center space-x-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span>सत्यापित व सहेजा गया / Confirmed & Applied</span>
                    </div>
                  ) : (
                    <div className="p-2 bg-slate-200 text-slate-600 rounded-lg text-center font-medium">
                      रद्द किया गया / Cancelled
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {isSending && (
          <div className="flex items-center space-x-3 text-slate-400 text-xs py-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-amber-500 to-green-600 flex items-center justify-center text-white">
              <Sparkles className="w-4 h-4 animate-spin" />
            </div>
            <div className="bg-slate-100 p-3 rounded-2xl rounded-tl-none border border-slate-200 flex items-center space-x-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-600" />
              <span>योजना सहायक सोच रहा है... / Assistant is thinking...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Questions Chips */}
      {messages.length <= 2 && (
        <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/50 flex flex-wrap gap-1.5">
          <button
            onClick={() => handleSendMessage(t('chat.suggest_kisan'))}
            className="px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 hover:border-orange-500 hover:text-orange-600 rounded-full shadow-sm transition-colors text-slate-700 flex items-center space-x-1"
          >
            <HelpCircle className="w-3 h-3 text-orange-500" />
            <span>{t('chat.suggest_kisan')}</span>
          </button>
          <button
            onClick={() => handleSendMessage(t('chat.suggest_ayushman'))}
            className="px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 hover:border-orange-500 hover:text-orange-600 rounded-full shadow-sm transition-colors text-slate-700 flex items-center space-x-1"
          >
            <HelpCircle className="w-3 h-3 text-blue-500" />
            <span>{t('chat.suggest_ayushman')}</span>
          </button>
          <button
            onClick={() => handleSendMessage(t('chat.suggest_svanidhi'))}
            className="px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 hover:border-orange-500 hover:text-orange-600 rounded-full shadow-sm transition-colors text-slate-700 flex items-center space-x-1"
          >
            <HelpCircle className="w-3 h-3 text-emerald-500" />
            <span>{t('chat.suggest_svanidhi')}</span>
          </button>
        </div>
      )}

      {/* Input Form Bar */}
      <div className="p-3 sm:p-4 border-t border-slate-200 bg-white">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center space-x-2"
        >
          <button
            type="button"
            onClick={handleVoiceInput}
            className={`p-2.5 rounded-xl border transition-colors ${
              isListening
                ? 'bg-rose-600 text-white border-rose-600 animate-pulse'
                : 'bg-slate-100 hover:bg-slate-200 text-slate-600 border-slate-200'
            }`}
            title="Voice input"
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4 text-orange-600" />}
          </button>

          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={t('chat.placeholder')}
            className="flex-1 py-2.5 px-3.5 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-600 transition-colors bg-slate-50/50"
          />

          <button
            type="submit"
            disabled={!inputText.trim() || isSending}
            className="p-2.5 bg-gradient-to-r from-orange-600 to-orange-500 hover:from-orange-700 hover:to-orange-600 text-white rounded-xl shadow-sm transition-all disabled:opacity-40"
            title={t('chat.send')}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

      {/* Real-time Voice Input Visualizer Modal */}
      <VoiceVisualizerModal
        isOpen={isVoiceModalOpen}
        interimTranscript={interimTranscript}
        onClose={handleCloseVoiceModal}
        onConfirm={handleConfirmVoiceModal}
      />
    </div>
  );
};
