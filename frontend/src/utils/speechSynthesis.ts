/**
 * Cross-browser Speech Synthesis (TTS) utility for Scheme Saathi.
 * Provides accessible, localized audio playback for Indian citizens.
 */

export interface SpeakOptions {
  lang?: 'hi-IN' | 'en-IN' | string;
  rate?: number;
  pitch?: number;
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (err: any) => void;
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined';
}

class SpeechSynthesizer {
  private activeUtterance: SpeechSynthesisUtterance | null = null;
  private isPlaying: boolean = false;
  private currentText: string | null = null;
  private voices: SpeechSynthesisVoice[] = [];

  constructor() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.loadVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = () => this.loadVoices();
      }
    }
  }

  private loadVoices(): void {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.voices = window.speechSynthesis.getVoices() || [];
    }
  }

  public getMatchingVoice(lang: string): SpeechSynthesisVoice | null {
    if (this.voices.length === 0) {
      this.loadVoices();
    }

    const isHindi = lang.toLowerCase().startsWith('hi');

    if (isHindi) {
      // 1. Exact hi-IN match
      const hiIn = this.voices.find((v) => v.lang === 'hi-IN' || v.lang === 'hi_IN');
      if (hiIn) return hiIn;

      // 2. Any Hindi voice
      const hiAny = this.voices.find(
        (v) => v.lang.toLowerCase().startsWith('hi') || v.name.toLowerCase().includes('hindi')
      );
      if (hiAny) return hiAny;
    } else {
      // 1. Indian English voice
      const enIn = this.voices.find((v) => v.lang === 'en-IN' || v.lang === 'en_IN');
      if (enIn) return enIn;

      // 2. Any English voice
      const enAny = this.voices.find((v) => v.lang.toLowerCase().startsWith('en'));
      if (enAny) return enAny;
    }

    return this.voices[0] || null;
  }

  public speak(text: string, options: SpeakOptions = {}): boolean {
    if (!isSpeechSynthesisSupported()) {
      options.onError?.(new Error('Speech synthesis is not supported.'));
      return false;
    }

    // Stop existing playback before speaking new text
    this.stop();

    if (!text || text.trim().length === 0) {
      return false;
    }

    try {
      const lang = options.lang || 'hi-IN';
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = options.rate ?? 0.95; // Slightly slower than 1.0 for rural clarity
      utterance.pitch = options.pitch ?? 1.0;

      const voice = this.getMatchingVoice(lang);
      if (voice) {
        utterance.voice = voice;
      }

      utterance.onstart = () => {
        this.isPlaying = true;
        this.currentText = text;
        options.onStart?.();
      };

      utterance.onend = () => {
        this.isPlaying = false;
        this.currentText = null;
        this.activeUtterance = null;
        options.onEnd?.();
      };

      utterance.onerror = (event) => {
        this.isPlaying = false;
        this.currentText = null;
        this.activeUtterance = null;
        options.onError?.(event);
      };

      this.activeUtterance = utterance;
      window.speechSynthesis.speak(utterance);
      return true;
    } catch (err) {
      this.isPlaying = false;
      this.currentText = null;
      options.onError?.(err);
      return false;
    }
  }

  public stop(): void {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // Safe ignore
      }
    }
    this.isPlaying = false;
    this.currentText = null;
    this.activeUtterance = null;
  }

  public pause(): void {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.pause();
    }
  }

  public resume(): void {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.resume();
    }
  }

  public isSpeaking(): boolean {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      return window.speechSynthesis.speaking;
    }
    return this.isPlaying;
  }

  public getActiveUtterance(): SpeechSynthesisUtterance | null {
    return this.activeUtterance;
  }

  public getCurrentText(): string | null {
    return this.currentText;
  }
}

export const speechSynthesizer = new SpeechSynthesizer();
