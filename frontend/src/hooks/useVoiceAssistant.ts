import { useState, useEffect, useRef, useCallback } from 'react';

// SpeechRecognition type definitions for standard & webkit implementations
interface IWindow extends Window {
  SpeechRecognition?: any;
  webkitSpeechRecognition?: any;
}

export type AssistantLanguage = 'auto' | 'mr' | 'hi' | 'en';

export interface UseVoiceAssistantReturn {
  // Speech Recognition (STT)
  isListening: boolean;
  isSttSupported: boolean;
  transcript: string;
  interimTranscript: string;
  sttError: string | null;
  startListening: (langPreference?: AssistantLanguage) => void;
  stopListening: () => void;
  resetTranscript: () => void;

  // Text to Speech (TTS)
  isSpeaking: boolean;
  isPaused: boolean;
  speakingMessageId: string | null;
  activeVoiceNotice: string | null;
  isTtsSupported: boolean;
  speak: (text: string, langCode: string, messageId: string) => void;
  pauseSpeaking: () => void;
  resumeSpeaking: () => void;
  stopSpeaking: () => void;
}

interface PlaybackQueueState {
  chunks: string[];
  currentIndex: number;
  messageId: string;
  langCode: string;
  targetLang: string;
  matchedVoice?: SpeechSynthesisVoice;
  isCancelled: boolean;
}

/**
 * Strips markdown symbols, raw URLs, and decorative icons for clean TTS speech
 * while preserving ALL substantive content: steps, numbers, bullet items, amounts, and conditions.
 */
export function cleanMarkdownForSpeech(text: string, langCode: string = 'en'): string {
  if (!text) return '';

  return text
    // Replace markdown links [label](url) with label (or 'official portal' if label is a url)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label) => {
      const trimmed = label.trim();
      if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
        if (langCode === 'mr') return 'अधिकृत पोर्टल';
        if (langCode === 'hi') return 'आधिकारिक पोर्टल';
        return 'official portal';
      }
      return trimmed;
    })
    // Remove bare URLs and any empty surrounding parentheses
    .replace(/\s*\(\s*https?:\/\/[^\s)]+\s*\)/g, '')
    .replace(/https?:\/\/[^\s)]+/g, '')
    .replace(/\(\s*\)/g, '')
    // Replace headings (### or ## or #)
    .replace(/#{1,6}\s+/g, '')
    // Remove bold and italics markers
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    // Remove inline code markers
    .replace(/`([^`]+)`/g, '$1')
    // Remove decorative emojis and bullet symbols
    .replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '')
    // Replace decorative bullets with clean pause/comma
    .replace(/^[ \t]*[•●○■◆]\s*/gm, '')
    // Normalize dashes at start of line
    .replace(/^[ \t]*[-*]\s+/gm, '')
    .trim();
}

/**
 * Splits text into natural, sequential speech chunks (100–180 characters)
 * to prevent browser TTS engines from timing out, stalling, or truncating audio.
 */
export function splitTextIntoSpeechChunks(text: string, langCode: string = 'en', maxLen: number = 180): string[] {
  const cleaned = cleanMarkdownForSpeech(text, langCode);
  if (!cleaned) return [];

  const paragraphs = cleaned.split(/\n+/);
  const rawChunks: string[] = [];

  for (const para of paragraphs) {
    const trimmedPara = para.trim();
    if (!trimmedPara) continue;

    // Split paragraph by sentences without splitting numbers like '1.', '2.', 'Rs.'
    const sentenceEndRegex = /(?<=[?!।॥])\s+|(?<!\b(?:[0-9]|rs|mr|mrs|dr|etc))\.\s+(?=[A-Z\u0900-\u097F])/i;
    const sentences = trimmedPara.split(sentenceEndRegex);

    for (const sentence of sentences) {
      const trimmedSentence = sentence.trim();
      if (!trimmedSentence) continue;

      if (trimmedSentence.length <= maxLen) {
        rawChunks.push(trimmedSentence);
      } else {
        // Split on clause punctuation: commas, semicolons, colons
        const clauses = trimmedSentence.split(/(?<=[,;:])\s+/);
        let current = '';
        for (const clause of clauses) {
          if (!current) {
            current = clause;
          } else if ((current + ' ' + clause).length <= maxLen) {
            current += ' ' + clause;
          } else {
            rawChunks.push(current.trim());
            current = clause;
          }
        }
        if (current.trim()) {
          if (current.length <= maxLen) {
            rawChunks.push(current.trim());
          } else {
            // Split on words if clause is still oversized
            const words = current.split(/\s+/);
            let sub = '';
            for (const w of words) {
              if (!sub) sub = w;
              else if ((sub + ' ' + w).length <= maxLen) sub += ' ' + w;
              else {
                rawChunks.push(sub);
                sub = w;
              }
            }
            if (sub) rawChunks.push(sub);
          }
        }
      }
    }
  }

  // Merge any tiny orphaned chunks (like "1." or "Note:") with the subsequent chunk
  const mergedChunks: string[] = [];
  for (let i = 0; i < rawChunks.length; i++) {
    const chunk = rawChunks[i];
    if (mergedChunks.length > 0 && mergedChunks[mergedChunks.length - 1].length + chunk.length + 1 <= maxLen) {
      const prev = mergedChunks[mergedChunks.length - 1];
      if (prev.endsWith(':') || /^\d+\.$/.test(prev) || prev.length < 15) {
        mergedChunks[mergedChunks.length - 1] = prev + ' ' + chunk;
        continue;
      }
    }
    mergedChunks.push(chunk);
  }

  return mergedChunks;
}

export const useVoiceAssistant = (): UseVoiceAssistantReturn => {
  // ── Speech to Text (STT) ────────────────────────────────────────────────
  const [isListening, setIsListening] = useState<boolean>(false);
  const [transcript, setTranscript] = useState<string>('');
  const [interimTranscript, setInterimTranscript] = useState<string>('');
  const [sttError, setSttError] = useState<string | null>(null);
  const [isSttSupported, setIsSttSupported] = useState<boolean>(false);

  const recognitionRef = useRef<any>(null);

  // ── Text to Speech (TTS) ────────────────────────────────────────────────
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [activeVoiceNotice, setActiveVoiceNotice] = useState<string | null>(null);
  const [isTtsSupported, setIsTtsSupported] = useState<boolean>(false);

  const availableVoicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const queueRef = useRef<PlaybackQueueState | null>(null);
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const keepAliveTimerRef = useRef<any>(null);
  const isPausedRef = useRef<boolean>(false);

  useEffect(() => {
    // Check Speech Recognition support in browser
    if (typeof window !== 'undefined') {
      const win = window as IWindow;
      const SpeechRecognitionConstructor = win.SpeechRecognition || win.webkitSpeechRecognition;
      if (SpeechRecognitionConstructor) {
        setIsSttSupported(true);
      }

      // Check Speech Synthesis support
      if ('speechSynthesis' in window) {
        setIsTtsSupported(true);
        const updateVoices = () => {
          availableVoicesRef.current = window.speechSynthesis.getVoices();
        };
        updateVoices();
        window.speechSynthesis.onvoiceschanged = updateVoices;
      }
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore cleanup errors
        }
      }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const getLocaleForLang = (lang?: AssistantLanguage): string => {
    switch (lang) {
      case 'mr':
        return 'mr-IN';
      case 'hi':
        return 'hi-IN';
      case 'en':
        return 'en-IN';
      default:
        return 'hi-IN'; // Default to Hindi-India for auto
    }
  };

  const startListening = useCallback((langPreference: AssistantLanguage = 'auto') => {
    setSttError(null);
    setTranscript('');
    setInterimTranscript('');

    const win = typeof window !== 'undefined' ? (window as IWindow) : null;
    const SpeechRecognitionConstructor = win?.SpeechRecognition || win?.webkitSpeechRecognition;

    if (!SpeechRecognitionConstructor) {
      setSttError('Speech recognition is not supported in this browser. Please use Chrome, Edge, or type your message.');
      return;
    }

    try {
      // Abort any active recognition
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }

      const recognition = new SpeechRecognitionConstructor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.lang = getLocaleForLang(langPreference);

      recognition.onstart = () => {
        setIsListening(true);
        setSttError(null);
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const item = event.results[i];
          if (item.isFinal) {
            final += item[0].transcript;
          } else {
            interim += item[0].transcript;
          }
        }

        if (final) {
          setTranscript((prev) => (prev ? `${prev} ${final}` : final).trim());
        }
        setInterimTranscript(interim);
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition event error:', event.error);
        if (event.error === 'not-allowed' || event.error === 'permission-denied') {
          setSttError('Microphone permission was denied. Please allow microphone access in your browser to speak.');
        } else if (event.error === 'no-speech') {
          setSttError('No speech detected. Please speak closer to your microphone.');
        } else if (event.error === 'network') {
          setSttError('Network connection issue during speech recognition. Please check your connection.');
        } else {
          setSttError(`Voice input error: ${event.error}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
        setInterimTranscript('');
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      console.error('Failed to start speech recognition:', err);
      setSttError(err?.message || 'Could not start voice recognition.');
      setIsListening(false);
    }
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    setIsListening(false);
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
    setSttError(null);
  }, []);

  // Keep-alive timer effect for Chromium 15-second hang prevention
  useEffect(() => {
    if (isSpeaking && !isPaused) {
      if (!keepAliveTimerRef.current) {
        keepAliveTimerRef.current = setInterval(() => {
          if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
              window.speechSynthesis.pause();
              window.speechSynthesis.resume();
            }
          }
        }, 10000);
      }
    } else {
      if (keepAliveTimerRef.current) {
        clearInterval(keepAliveTimerRef.current);
        keepAliveTimerRef.current = null;
      }
    }

    return () => {
      if (keepAliveTimerRef.current) {
        clearInterval(keepAliveTimerRef.current);
        keepAliveTimerRef.current = null;
      }
    };
  }, [isSpeaking, isPaused]);

  // ── Text to Speech Implementation with Sequential Chunking Queue ───────────
  const stopSpeaking = useCallback(() => {
    if (queueRef.current) {
      queueRef.current.isCancelled = true;
      queueRef.current = null;
    }
    if (keepAliveTimerRef.current) {
      clearInterval(keepAliveTimerRef.current);
      keepAliveTimerRef.current = null;
    }
    activeUtteranceRef.current = null;
    if (typeof window !== 'undefined') {
      (window as any).__ss_active_utterance = null;
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    }
    isPausedRef.current = false;
    setIsSpeaking(false);
    setIsPaused(false);
    setSpeakingMessageId(null);
    setActiveVoiceNotice(null);
  }, []);

  const playNextChunk = useCallback(() => {
    const queue = queueRef.current;
    if (!queue || queue.isCancelled || isPausedRef.current) {
      return;
    }

    if (queue.currentIndex >= queue.chunks.length) {
      // Completed full sequential playback of all chunks
      if (keepAliveTimerRef.current) {
        clearInterval(keepAliveTimerRef.current);
        keepAliveTimerRef.current = null;
      }
      queueRef.current = null;
      activeUtteranceRef.current = null;
      if (typeof window !== 'undefined') {
        (window as any).__ss_active_utterance = null;
      }
      isPausedRef.current = false;
      setIsSpeaking(false);
      setIsPaused(false);
      setSpeakingMessageId(null);
      setActiveVoiceNotice(null);
      return;
    }

    const chunkText = queue.chunks[queue.currentIndex];
    const utterance = new SpeechSynthesisUtterance(chunkText);
    utterance.lang = queue.targetLang;
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    if (queue.matchedVoice) {
      utterance.voice = queue.matchedVoice;
    }

    // Retain strong reference against Chromium garbage collection
    activeUtteranceRef.current = utterance;
    if (typeof window !== 'undefined') {
      (window as any).__ss_active_utterance = utterance;
    }

    utterance.onstart = () => {
      setIsSpeaking(true);
      setIsPaused(false);
      isPausedRef.current = false;
      setSpeakingMessageId(queue.messageId);
    };

    utterance.onend = () => {
      if (queueRef.current && !queueRef.current.isCancelled && !isPausedRef.current) {
        queueRef.current.currentIndex += 1;
        playNextChunk();
      }
    };

    utterance.onerror = (event: any) => {
      if (queueRef.current?.isCancelled) {
        return;
      }
      console.warn(`TTS Chunk ${queue.currentIndex} event error:`, event?.error);
      // Gracefully advance to next chunk so subsequent speech is not lost
      if (queueRef.current && !queueRef.current.isCancelled && !isPausedRef.current) {
        queueRef.current.currentIndex += 1;
        playNextChunk();
      }
    };

    window.speechSynthesis.speak(utterance);
  }, []);

  const speak = useCallback((text: string, langCode: string, messageId: string) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      console.warn('Speech synthesis not available.');
      return;
    }

    // Cancel any existing playback cleanly
    stopSpeaking();

    if (!text || !text.trim()) return;

    const chunks = splitTextIntoSpeechChunks(text, langCode);
    if (chunks.length === 0) return;

    // Map language code to BCP 47
    let targetLang = 'hi-IN';
    if (langCode === 'mr') targetLang = 'mr-IN';
    else if (langCode === 'en') targetLang = 'en-IN';
    else if (langCode === 'hi') targetLang = 'hi-IN';

    // Pick best matching voice
    const voices = availableVoicesRef.current.length > 0 ? availableVoicesRef.current : window.speechSynthesis.getVoices();
    let matchedVoice: SpeechSynthesisVoice | undefined;

    if (targetLang === 'mr-IN') {
      const nativeMr = voices.find((v) => v.lang.toLowerCase() === 'mr-in' || v.lang.toLowerCase().startsWith('mr'));
      if (nativeMr) {
        matchedVoice = nativeMr;
        setActiveVoiceNotice(null);
      } else {
        matchedVoice =
          voices.find((v) => v.lang.toLowerCase() === 'hi-in' || v.lang.toLowerCase().startsWith('hi')) ||
          voices.find((v) => v.lang.toLowerCase().includes('in'));
        setActiveVoiceNotice('मराठी उच्चार: हिंदी आवाज (Lekha) द्वारे उपलब्ध (ब्राउझरमध्ये मूळ मराठी व्हॉइस उपलब्ध नाही)');
      }
    } else if (targetLang === 'hi-IN') {
      matchedVoice =
        voices.find((v) => v.lang.toLowerCase() === 'hi-in' || v.lang.toLowerCase().startsWith('hi')) ||
        voices.find((v) => v.lang.toLowerCase().includes('in'));
      setActiveVoiceNotice(null);
    } else {
      matchedVoice =
        voices.find((v) => v.lang.toLowerCase() === 'en-in') ||
        voices.find((v) => v.lang.toLowerCase().startsWith('en')) ||
        voices.find((v) => v.lang.toLowerCase().includes('in'));
      setActiveVoiceNotice(null);
    }

    // Initialize queue state
    queueRef.current = {
      chunks,
      currentIndex: 0,
      messageId,
      langCode,
      targetLang,
      matchedVoice,
      isCancelled: false,
    };
    isPausedRef.current = false;
    setIsSpeaking(true);
    setIsPaused(false);
    setSpeakingMessageId(messageId);

    // Play first chunk
    playNextChunk();
  }, [stopSpeaking, playNextChunk]);

  const pauseSpeaking = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      isPausedRef.current = true;
      setIsPaused(true);
      window.speechSynthesis.pause();
    }
  }, []);

  const resumeSpeaking = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      isPausedRef.current = false;
      setIsPaused(false);
      window.speechSynthesis.resume();

      // Fallback for Chromium resume bug: if speech does not resume within 150ms, re-invoke playNextChunk
      setTimeout(() => {
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
          if (!window.speechSynthesis.speaking && queueRef.current && !queueRef.current.isCancelled) {
            playNextChunk();
          }
        }
      }, 150);
    }
  }, [playNextChunk]);

  return {
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
    isTtsSupported,
    speak,
    pauseSpeaking,
    resumeSpeaking,
    stopSpeaking,
  };
};
