import React from 'react';
import { Mic, Check, X } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

interface VoiceVisualizerModalProps {
  isOpen: boolean;
  interimTranscript: string;
  onClose: () => void;
  onConfirm: () => void;
}

export const VoiceVisualizerModal: React.FC<VoiceVisualizerModalProps> = ({
  isOpen,
  interimTranscript,
  onClose,
  onConfirm,
}) => {
  const { language } = useLanguage();

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-label="Voice input visualizer"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in"
    >
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-200 p-6 space-y-6 animate-slide-up">
        {/* Header / Animated Mic Pulse */}
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="relative">
            <div className="w-16 h-16 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 animate-pulse">
              <Mic className="w-8 h-8" />
            </div>
            {/* Audio wave rings */}
            <span className="absolute -inset-2 rounded-full border-2 border-orange-400/40 animate-ping" />
          </div>

          <div>
            <h3 className="text-base font-bold text-slate-900">
              {language === 'hi' ? 'आपकी आवाज सुनी जा रही है...' : 'Listening to your voice...'}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {language === 'hi'
                ? 'कृपया साफ आवाज में अपनी योजना या प्रश्न बताएं'
                : 'Please speak clearly about your scheme or inquiry'}
            </p>
          </div>
        </div>

        {/* Live Transcript Display Box */}
        <div className="min-h-[96px] p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-col justify-center text-center">
          {interimTranscript ? (
            <p className="text-sm font-semibold text-slate-900 leading-relaxed">
              "{interimTranscript}"
            </p>
          ) : (
            <div className="flex items-center justify-center space-x-1.5 text-slate-400 text-xs">
              <span className="inline-block w-2 h-2 rounded-full bg-orange-500 animate-bounce" />
              <span className="inline-block w-2 h-2 rounded-full bg-orange-500 animate-bounce delay-150" />
              <span className="inline-block w-2 h-2 rounded-full bg-orange-500 animate-bounce delay-300" />
              <span className="ml-2">
                {language === 'hi' ? 'बोलना शुरू करें...' : 'Start speaking...'}
              </span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 px-4 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5"
          >
            <X className="w-4 h-4" />
            <span>{language === 'hi' ? 'रद्द करें' : 'Cancel'}</span>
          </button>

          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 py-2.5 px-4 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-md shadow-orange-500/20 transition-colors flex items-center justify-center space-x-1.5"
          >
            <Check className="w-4 h-4" />
            <span>{language === 'hi' ? 'पूरा हुआ / भेजें' : 'Done / Submit'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
