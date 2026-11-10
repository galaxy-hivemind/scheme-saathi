import React, { useState, useRef, useEffect } from 'react';
import { agentService } from '@/services/api/agentService';
import { ChatMessage, Scheme, DocumentRequirement } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { Button } from '@/components/common/Button';
import { Card, CardContent } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Send, Sparkles, User, FileText, ArrowRight, Bot, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

export const ChatPage: React.FC = () => {
  const { t, language } = useLanguage();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-01',
      conversation_id: 'conv-init',
      role: 'assistant',
      message_content:
        language === 'hi'
          ? 'नमस्ते! मैं आपका योजना साथी हूँ। मैं आपके लिए सरकारी योजनाएं खोजने, पात्रता परखने और दस्तावेज़ तैयार करने में सहायता कर सकता हूँ। आप किस विषय में जानना चाहते हैं?'
          : 'Hello! I am Scheme Saathi, your dedicated welfare assistance companion. Tell me about your occupation, family income, or questions, and I will help you discover eligible government schemes.',
      response_type: 'text',
      created_at: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const suggestedPrompts = [
    { hi: 'मुझे किसानों के लिए योजनाएं बताओ', en: 'Tell me about schemes for farmers' },
    { hi: 'क्या मैं छात्रवृत्ति (Scholarship) के लिए पात्र हूँ?', en: 'Am I eligible for any scholarship?' },
    { hi: 'PM-KISAN के लिए कौन से दस्तावेज़ चाहिए?', en: 'What documents are required for PM-KISAN?' },
    { hi: 'आवास योजना (PMAY) का लाभ कैसे लें?', en: 'How can I get benefits under PMAY Housing?' },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (messageText: string) => {
    if (!messageText.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      conversation_id: 'conv-active',
      role: 'user',
      message_content: messageText,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await agentService.sendMessage(messageText, 'conv-active', language);

      const assistantMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        conversation_id: response.conversation_id,
        role: 'assistant',
        message_content: response.message,
        response_type: response.response_type,
        data: response.data,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error('Chat error:', err);
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        conversation_id: 'conv-active',
        role: 'assistant',
        message_content:
          language === 'hi'
            ? 'क्षमा करें, संदेश संसाधित करने में समस्या हुई। कृपया पुनः प्रयास करें।'
            : 'Sorry, I encountered an issue processing your request. Please try again.',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const renderStructuredData = (msg: ChatMessage) => {
    if (msg.response_type === 'scheme_cards' && Array.isArray(msg.data)) {
      return (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 w-full">
          {(msg.data as Scheme[]).map((scheme) => (
            <Card key={scheme.id} className="border border-navy/10 shadow-subtle hover:shadow-premium bg-white">
              <CardContent className="p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <Badge variant="category">{scheme.category}</Badge>
                  <span className="text-[10px] text-sage-green font-semibold bg-sage-light px-2 py-0.5 rounded-full border border-sage/30">
                    {scheme.scheme_code}
                  </span>
                </div>
                <h4 className="font-bold text-navy text-xs sm:text-sm line-clamp-1 font-editorial">{scheme.name}</h4>
                <p className="text-[11px] text-navy/70 line-clamp-2 leading-relaxed">{scheme.benefits}</p>
                <div className="pt-2 flex items-center justify-between border-t border-navy/6">
                  <Link
                    to={`/schemes/${scheme.id}`}
                    className="text-xs font-bold text-saffron-dark hover:text-saffron flex items-center gap-1 group/link"
                  >
                    <span>{t.actions.viewDetails}</span>
                    <ArrowRight className="w-3 h-3 transition-transform group-hover/link:translate-x-0.5" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      );
    }

    if (msg.response_type === 'document_checklist' && Array.isArray(msg.data)) {
      return (
        <div className="space-y-2 mt-3 w-full">
          {(msg.data as DocumentRequirement[]).map((doc) => (
            <div key={doc.id} className="flex items-center justify-between p-3 rounded-xl bg-white border border-navy/10 text-xs shadow-subtle">
              <div className="flex items-center gap-2.5">
                <FileText className="w-4 h-4 text-saffron" />
                <span className="font-semibold capitalize text-navy">{doc.document_type.replace(/_/g, ' ')}</span>
              </div>
              <Badge variant={doc.is_mandatory ? 'saffron' : 'category'}>
                {doc.is_mandatory ? 'Mandatory' : 'Optional'}
              </Badge>
            </div>
          ))}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col h-[calc(100vh-190px)] min-h-[520px] bg-white rounded-3xl border border-navy/8 shadow-subtle overflow-hidden">
      {/* Chat Header */}
      <div className="px-6 py-4 border-b border-navy/8 bg-ivory-50/70 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-navy text-white flex items-center justify-center shadow-subtle">
            <Bot className="w-5 h-5 text-saffron" />
          </div>
          <div>
            <h2 className="text-sm font-bold font-editorial text-navy flex items-center gap-2">
              <span>{t.nav.chat}</span>
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-sage-green bg-sage-light px-2 py-0.5 rounded-full border border-sage/30">
                <span className="w-1.5 h-1.5 rounded-full bg-sage-green animate-pulse" />
                Active Companion
              </span>
            </h2>
            <p className="text-[11px] text-navy/50">Gemini Orchestrated • Deterministic Rule Verification</p>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-1.5 text-xs text-navy/60 font-medium">
          <ShieldCheck className="w-4 h-4 text-sage" />
          <span>Strict Privacy</span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-ivory-50/30">
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          return (
            <div key={msg.id} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
              {!isUser && (
                <div className="w-8 h-8 rounded-full bg-saffron-light text-saffron-dark flex items-center justify-center shrink-0 mt-0.5 border border-saffron/30 shadow-subtle">
                  <Sparkles className="w-4 h-4 text-saffron-vibrant" />
                </div>
              )}

              <div
                className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 text-sm leading-relaxed transition-all duration-200 ${
                  isUser
                    ? 'bg-navy text-white rounded-tr-xs shadow-subtle'
                    : 'bg-white text-navy rounded-tl-xs border border-navy/8 shadow-subtle'
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{msg.message_content}</p>
                {renderStructuredData(msg)}
                <span
                  className={`block text-[10px] mt-2 text-right ${
                    isUser ? 'text-white/60' : 'text-navy/40'
                  }`}
                >
                  {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
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
            <span>साथी सोच रहा है... (Verifying official rules and guidelines...)</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompt Chips */}
      <div className="px-5 py-2.5 border-t border-navy/8 bg-ivory/60 flex items-center gap-2 overflow-x-auto scrollbar-none">
        {suggestedPrompts.map((p, idx) => {
          const text = language === 'hi' ? p.hi : p.en;
          return (
            <button
              key={idx}
              onClick={() => handleSend(text)}
              className="text-xs px-3.5 py-1.5 rounded-full bg-white text-navy/80 border border-navy/12 hover:border-saffron hover:text-saffron-dark transition-all duration-200 whitespace-nowrap shrink-0 shadow-subtle"
            >
              {text}
            </button>
          );
        })}
      </div>

      {/* Input Form Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
        className="p-3 sm:p-4 border-t border-navy/8 bg-white flex items-center gap-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={language === 'hi' ? 'साथी से पूछें (उदा. क्या मैं छात्रवृत्ति के योग्य हूँ?)...' : 'Ask Scheme Saathi anything about eligibility, criteria, or documents...'}
          className="flex-1 bg-ivory-50 border border-navy/15 rounded-xl px-4 py-2.5 text-sm text-navy placeholder-navy/40 focus:outline-none focus:ring-2 focus:ring-navy/15 focus:border-navy transition-all"
        />
        <Button type="submit" variant="saffron" size="md" disabled={!input.trim() || loading} className="shrink-0 px-5">
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </div>
  );
};
