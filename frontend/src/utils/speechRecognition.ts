/**
 * Cross-browser Speech Recognition wrapper for Scheme Saathi.
 * Supports standard W3C SpeechRecognition and webkitSpeechRecognition.
 */

export interface SpeechRecognitionCallbacks {
  onStart?: () => void;
  onInterimResult?: (interimTranscript: string) => void;
  onFinalResult?: (finalTranscript: string) => void;
  onError?: (error: any) => void;
  onEnd?: () => void;
}

export interface SpeechRecognitionOptions {
  lang?: 'hi-IN' | 'en-IN' | string;
  continuous?: boolean;
  interimResults?: boolean;
  maxAlternatives?: number;
}

export function isSpeechRecognitionSupported(): boolean {
  if (typeof window === 'undefined') return false;
  return !!(
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition
  );
}

export class SpeechRecognizer {
  private recognition: any = null;
  private listening: boolean = false;
  private callbacks: SpeechRecognitionCallbacks;
  private options: SpeechRecognitionOptions;

  constructor(
    callbacks: SpeechRecognitionCallbacks,
    options: SpeechRecognitionOptions = {}
  ) {
    this.callbacks = callbacks;
    this.options = {
      lang: 'hi-IN',
      continuous: false,
      interimResults: true,
      maxAlternatives: 1,
      ...options,
    };
  }

  public isListening(): boolean {
    return this.listening;
  }

  public start(): boolean {
    if (typeof window === 'undefined') return false;

    const SpeechRecognitionClass =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognitionClass) {
      if (this.callbacks.onError) {
        this.callbacks.onError(new Error('Speech recognition is not supported in this browser.'));
      }
      return false;
    }

    try {
      this.recognition = new SpeechRecognitionClass();
      this.recognition.lang = this.options.lang || 'hi-IN';
      this.recognition.continuous = !!this.options.continuous;
      this.recognition.interimResults = this.options.interimResults !== false;
      this.recognition.maxAlternatives = this.options.maxAlternatives || 1;

      this.recognition.onstart = () => {
        this.listening = true;
        this.callbacks.onStart?.();
      };

      this.recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';

        const startIndex = event.resultIndex || 0;
        for (let i = startIndex; i < event.results.length; ++i) {
          const item = event.results[i];
          const transcript = item[0]?.transcript || '';
          if (item.isFinal === false) {
            interim += transcript;
          } else {
            final += transcript;
          }
        }

        if (interim && this.callbacks.onInterimResult) {
          this.callbacks.onInterimResult(interim.trim());
        }
        if (final && this.callbacks.onFinalResult) {
          this.callbacks.onFinalResult(final.trim());
        }
      };

      this.recognition.onerror = (event: any) => {
        this.listening = false;
        this.callbacks.onError?.(event);
      };

      this.recognition.onend = () => {
        this.listening = false;
        this.callbacks.onEnd?.();
      };

      this.recognition.start();
      return true;
    } catch (err) {
      this.listening = false;
      this.callbacks.onError?.(err);
      return false;
    }
  }

  public stop(): void {
    if (this.recognition && this.listening) {
      try {
        this.recognition.stop();
      } catch (e) {
        // Ignore if already stopped
      }
    }
    this.listening = false;
  }

  public abort(): void {
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (e) {
        // Ignore if already stopped
      }
    }
    this.listening = false;
  }

  public setLanguage(lang: 'hi-IN' | 'en-IN' | string): void {
    this.options.lang = lang;
    if (this.recognition) {
      this.recognition.lang = lang;
    }
  }
}
